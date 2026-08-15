"""`parse_document` for `source_type=url` documents that turn out to point at
a FILE (docs/ingestion.md 網址（檔案）) — the gap this feature closes.

Runs the real job handler (`backend.jobs.worker.run_claimed_job` ->
`backend.ingestion.pipeline.parse_document`) end to end against a throwaway
local HTTP server (`http.server.ThreadingHTTPServer`, real socket, real
Content-Type headers) so the routing decision, the streaming download, the
size-cap abort and the on-disk storage are all really executed — only the
LLM transport is faked (`httpx2.MockTransport`, same pattern as
`test_ingestion_rechunk.py`), per task instructions (no live LLM calls).

The file kind under test is Word: mammoth's real conversion needs no vision
call at all, so only the chunk-phase's classify/embed calls need mocking —
keeping the fake LLM handler simple while still exercising the real,
unduplicated `_process_document_by_kind` path shared with uploads.
"""

import io
import json
import zipfile
from collections.abc import Callable, Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import httpx2
import openai
import pytest
from factories import create_job
from sqlalchemy import select

import backend.ingestion.pipeline as pipeline_module
from backend.core.config import Settings, get_settings
from backend.db.session import AsyncSessionLocal
from backend.jobs.worker import claim_job, run_claimed_job
from backend.llm.client import LLMClient
from backend.models.chunk import Chunk
from backend.models.document import Document
from backend.models.job import Job
from backend.models.page import Page

# ---------------------------------------------------------------------------
# A minimal but real, valid `.docx` (same technique as test_ingestion_word.py).
# ---------------------------------------------------------------------------

_RELS_CONTENT_TYPE = "application/vnd.openxmlformats-package.relationships+xml"
_MAIN_DOCUMENT_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
)
_OFFICE_DOCUMENT_REL_TYPE = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
)
_WORD_MIME_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

_CONTENT_TYPES_XML = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="{_RELS_CONTENT_TYPE}"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="{_MAIN_DOCUMENT_CONTENT_TYPE}"/>
</Types>"""

_PACKAGE_RELS_XML = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="{_OFFICE_DOCUMENT_REL_TYPE}" Target="word/document.xml"/>
</Relationships>"""

_DOCUMENT_XML_TEMPLATE = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>{body}</w:body>
</w:document>"""


def _paragraph_xml(text: str) -> str:
    return f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>"


def _build_docx_bytes(paragraph_text: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", _CONTENT_TYPES_XML)
        archive.writestr("_rels/.rels", _PACKAGE_RELS_XML)
        archive.writestr(
            "word/document.xml",
            _DOCUMENT_XML_TEMPLATE.format(body=_paragraph_xml(paragraph_text)),
        )
    return buffer.getvalue()


_DOCX_PARAGRAPH_TEXT = "這份文件從網址下載後應該走上傳檔案同一條 Word 管線。"
_DOCX_BYTES = _build_docx_bytes(_DOCX_PARAGRAPH_TEXT)

# ---------------------------------------------------------------------------
# Throwaway local HTTP server (real socket, real headers).
# ---------------------------------------------------------------------------


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:  # noqa: A002 - stdlib signature
        pass  # keep test output quiet

    def _respond(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _route(self) -> None:
        if self.path == "/notes.docx":
            self._respond(200, _WORD_MIME_TYPE, _DOCX_BYTES)
        elif self.path == "/big-notes.docx":
            self._respond(200, _WORD_MIME_TYPE, _DOCX_BYTES * 200)
        elif self.path == "/archive.zip":
            self._respond(200, "application/zip", b"PK\x03\x04 fake zip body")
        elif self.path == "/article.html":
            body = (
                "<html><head><title>光合作用</title></head><body>"
                "<article><h1>光合作用</h1><p>" + ("光合作用發生在葉綠體。" * 20) + "</p>"
                "</article></body></html>"
            ).encode("utf-8")
            self._respond(200, "text/html; charset=utf-8", body)
        elif self.path == "/posts/%E7%B4%B0%E8%83%9E%E5%91%BC%E5%90%B8%E4%BD%9C%E7%94%A8":
            # No <title>/metadata at all -- exercises the URL-path-segment
            # fallback. The path segment is itself percent-encoded Chinese
            # (as a real blog slug often is), so the fallback must decode it.
            body = (
                "<html><body><article><p>"
                + ("細胞呼吸作用發生在粒線體。" * 20)
                + "</p></article></body></html>"
            ).encode("utf-8")
            self._respond(200, "text/html; charset=utf-8", body)
        else:
            self._respond(404, "text/plain", b"not found")

    def do_HEAD(self) -> None:  # noqa: N802 - stdlib method name
        self._route()

    def do_GET(self) -> None:  # noqa: N802 - stdlib method name
        self._route()


@pytest.fixture
def local_server() -> Iterator[str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join()


# ---------------------------------------------------------------------------
# Fake LLM transport (httpx2.MockTransport, same pattern as
# test_ingestion_rechunk.py) — distinguishes classify vs. summarize calls by
# the `response_format.json_schema.name` the client sends.
# ---------------------------------------------------------------------------


def _chat_completion_response(*, model: str, content: dict[str, object]) -> httpx2.Response:
    return httpx2.Response(
        200,
        json={
            "id": "chatcmpl-test",
            "object": "chat.completion",
            "created": 0,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": json.dumps(content)},
                }
            ],
            "usage": {"prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 7},
        },
    )


def _embeddings_response(*, model: str, dim: int) -> httpx2.Response:
    return httpx2.Response(
        200,
        json={
            "object": "list",
            "model": model,
            "data": [{"object": "embedding", "index": 0, "embedding": [0.0] * dim}],
            "usage": {"prompt_tokens": 2, "total_tokens": 2},
        },
    )


def _fake_llm_handler(dim: int) -> Callable[[httpx2.Request], httpx2.Response]:
    def handler(request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content)
        if request.url.path == "/v1/embeddings":
            return _embeddings_response(model=body["model"], dim=dim)

        schema_name = body["response_format"]["json_schema"]["name"]
        if schema_name == "TitleAndSummaryResult":
            content: dict[str, object] = {"title": "光合作用完整教學", "summary": "光合作用摘要"}
        elif schema_name == "ChunkClassification":
            content = {
                "subject": "生物",
                "topic": "光合作用",
                "difficulty": "中等",
                "tags": ["葉綠體"],
            }
        else:
            raise AssertionError(f"unexpected response_format schema: {schema_name!r}")
        return _chat_completion_response(model=body["model"], content=content)

    return handler


def _fake_llm_handler_blank_title(dim: int) -> Callable[[httpx2.Request], httpx2.Response]:
    """Same as `_fake_llm_handler`, except the title+summary call succeeds
    but comes back with a whitespace-only title -- exercises the "title
    comes back empty/whitespace" fallback branch, distinct from an outright
    call failure."""

    def handler(request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content)
        if request.url.path == "/v1/embeddings":
            return _embeddings_response(model=body["model"], dim=dim)

        schema_name = body["response_format"]["json_schema"]["name"]
        if schema_name == "TitleAndSummaryResult":
            content: dict[str, object] = {"title": "   ", "summary": "光合作用摘要"}
        elif schema_name == "ChunkClassification":
            content = {
                "subject": "生物",
                "topic": "光合作用",
                "difficulty": "中等",
                "tags": ["葉綠體"],
            }
        else:
            raise AssertionError(f"unexpected response_format schema: {schema_name!r}")
        return _chat_completion_response(model=body["model"], content=content)

    return handler


def _fake_llm_handler_title_failure(dim: int) -> Callable[[httpx2.Request], httpx2.Response]:
    """Same as `_fake_llm_handler`, except the title+summary call itself
    fails schema validation (missing the required `summary` field) --
    exercises the "call fails outright" fallback branch: `LLMClient.chat`
    raises `LLMResponseError`, which the pipeline must catch instead of
    failing the whole ingestion job."""

    def handler(request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content)
        if request.url.path == "/v1/embeddings":
            return _embeddings_response(model=body["model"], dim=dim)

        schema_name = body["response_format"]["json_schema"]["name"]
        if schema_name == "TitleAndSummaryResult":
            content: dict[str, object] = {"title": "光合作用"}  # missing required "summary"
        elif schema_name == "ChunkClassification":
            content = {
                "subject": "生物",
                "topic": "光合作用",
                "difficulty": "中等",
                "tags": ["葉綠體"],
            }
        else:
            raise AssertionError(f"unexpected response_format schema: {schema_name!r}")
        return _chat_completion_response(model=body["model"], content=content)

    return handler


def _fake_llm_client(handler: Callable[[httpx2.Request], httpx2.Response]) -> LLMClient:
    settings = Settings(
        llm_base_url="https://llm.test/v1", llm_api_key="test-key-not-real", text_model="test-text"
    )
    fake_openai_client = openai.AsyncOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler)),
    )
    return LLMClient(
        settings=settings, session_factory=AsyncSessionLocal, openai_client=fake_openai_client
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _make_url_document(url: str) -> int:
    async with AsyncSessionLocal() as session:
        # Mirrors what `POST /v1/documents/url` actually stores when no
        # custom title is given: title falls back to the raw URL string.
        document = Document(source_type="url", title=url, status="pending", source_url=url)
        session.add(document)
        await session.commit()
        await session.refresh(document)
        return document.id


async def _run_parse_document_job(document_id: int) -> Job:
    job_id = await create_job("parse_document", payload={"document_id": document_id})
    async with AsyncSessionLocal() as session:
        claimed = await claim_job(session)
        assert claimed is not None
        assert claimed.id == job_id
    await run_claimed_job(AsyncSessionLocal, job_id)
    async with AsyncSessionLocal() as session:
        job = await session.get(Job, job_id)
        assert job is not None
        return job


@pytest.fixture(autouse=True)
def _isolated_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    yield tmp_path
    get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_url_document_pointing_at_word_file_downloads_and_uses_word_pipeline(
    local_server: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = f"{local_server}/notes.docx"
    document_id = await _make_url_document(url)

    dim = Settings().embedding_dim
    fake_client = _fake_llm_client(_fake_llm_handler(dim))
    monkeypatch.setattr(pipeline_module, "get_llm_client", lambda: fake_client)

    job = await _run_parse_document_job(document_id)
    assert job.status == "done", job.error

    async with AsyncSessionLocal() as session:
        document = await session.get(Document, document_id)
        assert document is not None
        assert document.status == "ready"
        # source_type stays 'url'; source_url is preserved (docs/ingestion.md).
        assert document.source_type == "url"
        assert document.source_url == url
        # A reasonable title was derived from the filename (no custom title
        # was given at creation, so title had defaulted to the raw URL).
        assert document.title == "notes.docx"

        assert document.raw_file_path is not None
        raw_path = Path(document.raw_file_path)
        assert raw_path.is_file()
        assert raw_path.read_bytes() == _DOCX_BYTES
        # Landed under DATA_DIR/uploads, same layout an upload would use.
        assert tmp_path / "uploads" in raw_path.parents

    # Word extraction (mammoth) ran for real — the actual paragraph text
    # from the downloaded file made it into the page markdown.
    async with AsyncSessionLocal() as session:
        page_rows = (
            (await session.execute(select(Page).where(Page.document_id == document_id)))
            .scalars()
            .all()
        )
        assert len(page_rows) == 1
        assert page_rows[0].status == "ready"
        assert page_rows[0].markdown is not None
        assert _DOCX_PARAGRAPH_TEXT in page_rows[0].markdown

        chunk_rows = (
            (await session.execute(select(Chunk).where(Chunk.document_id == document_id)))
            .scalars()
            .all()
        )
        assert len(chunk_rows) >= 1


async def test_url_document_file_download_aborts_when_exceeding_max_bytes(
    local_server: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("URL_FETCH_MAX_BYTES", "1024")
    get_settings.cache_clear()

    url = f"{local_server}/big-notes.docx"
    document_id = await _make_url_document(url)

    dim = Settings().embedding_dim
    fake_client = _fake_llm_client(_fake_llm_handler(dim))
    monkeypatch.setattr(pipeline_module, "get_llm_client", lambda: fake_client)

    job = await _run_parse_document_job(document_id)

    assert job.status == "failed"
    assert job.error is not None
    assert "URL_FETCH_MAX_BYTES" in job.error

    async with AsyncSessionLocal() as session:
        document = await session.get(Document, document_id)
        assert document is not None
        assert document.status == "failed"
        assert document.raw_file_path is None  # aborted before anything was written to disk

    get_settings.cache_clear()


async def test_url_document_unsupported_content_type_fails_job_with_clear_message(
    local_server: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = f"{local_server}/archive.zip"
    document_id = await _make_url_document(url)

    dim = Settings().embedding_dim
    fake_client = _fake_llm_client(_fake_llm_handler(dim))
    monkeypatch.setattr(pipeline_module, "get_llm_client", lambda: fake_client)

    job = await _run_parse_document_job(document_id)

    assert job.status == "failed"
    assert job.error is not None
    assert "unsupported content-type" in job.error.lower()
    assert "application/zip" in job.error

    async with AsyncSessionLocal() as session:
        document = await session.get(Document, document_id)
        assert document is not None
        assert document.status == "failed"
        assert document.raw_file_path is None


async def test_url_document_webpage_title_and_summary_come_from_llm(
    local_server: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """docs/ingestion.md 網址（網頁）— an HTML page still goes through
    trafilatura, then one combined `TEXT_MODEL` call producing BOTH
    `documents.title` and `documents.summary` (docs/ingestion.md 網頁線的摘
    要用途界定). The LLM title overwrites the URL/metadata-derived fallback
    outright — it is not merely used when metadata has no `<title>`."""
    url = f"{local_server}/article.html"
    document_id = await _make_url_document(url)

    dim = Settings().embedding_dim
    fake_client = _fake_llm_client(_fake_llm_handler(dim))
    monkeypatch.setattr(pipeline_module, "get_llm_client", lambda: fake_client)

    job = await _run_parse_document_job(document_id)
    assert job.status == "done", job.error

    async with AsyncSessionLocal() as session:
        document = await session.get(Document, document_id)
        assert document is not None
        assert document.status == "ready"
        assert document.raw_file_path is None  # no file was ever downloaded
        assert document.summary == "光合作用摘要"
        # From the LLM call, not the page's real <title> ("光合作用") nor the
        # raw URL -- the LLM title overwrites the metadata-derived fallback.
        assert document.title == "光合作用完整教學"

        page_rows = (
            (await session.execute(select(Page).where(Page.document_id == document_id)))
            .scalars()
            .all()
        )
        assert len(page_rows) == 1
        assert "光合作用" in (page_rows[0].markdown or "")


async def test_url_document_webpage_llm_call_failure_falls_back_to_derived_title(
    local_server: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """docs/ingestion.md — a broken title+summary call (schema validation
    failure here, via a response missing the required `summary` field) must
    not fail the whole ingestion job: the document still reaches `ready`
    with its page/chunks, falling back to the URL-path-segment-derived title
    (`derive_webpage_title`, decoding the percent-encoded Chinese slug) and
    no summary."""
    url = f"{local_server}/posts/%E7%B4%B0%E8%83%9E%E5%91%BC%E5%90%B8%E4%BD%9C%E7%94%A8"
    document_id = await _make_url_document(url)

    dim = Settings().embedding_dim
    fake_client = _fake_llm_client(_fake_llm_handler_title_failure(dim))
    monkeypatch.setattr(pipeline_module, "get_llm_client", lambda: fake_client)

    job = await _run_parse_document_job(document_id)
    assert job.status == "done", job.error

    async with AsyncSessionLocal() as session:
        document = await session.get(Document, document_id)
        assert document is not None
        assert document.status == "ready"
        assert document.title == "細胞呼吸作用"  # URL-path-segment fallback, not the LLM
        assert document.summary is None  # the failed call never set it


async def test_url_document_webpage_blank_llm_title_falls_back_to_derived_title(
    local_server: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The title+summary call succeeds but the title comes back
    whitespace-only -- title falls back to the URL-derived one, but the
    summary (which did come back fine) is still saved (docs/ingestion.md —
    only the title half degrades, not the whole call's result)."""
    url = f"{local_server}/posts/%E7%B4%B0%E8%83%9E%E5%91%BC%E5%90%B8%E4%BD%9C%E7%94%A8"
    document_id = await _make_url_document(url)

    dim = Settings().embedding_dim
    fake_client = _fake_llm_client(_fake_llm_handler_blank_title(dim))
    monkeypatch.setattr(pipeline_module, "get_llm_client", lambda: fake_client)

    job = await _run_parse_document_job(document_id)
    assert job.status == "done", job.error

    async with AsyncSessionLocal() as session:
        document = await session.get(Document, document_id)
        assert document is not None
        assert document.status == "ready"
        assert document.title == "細胞呼吸作用"  # URL-path-segment fallback, not blank
        assert document.summary == "光合作用摘要"  # summary half still saved
