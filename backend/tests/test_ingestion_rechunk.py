"""`rechunk_document` job handler (.rule 反偷懶規則 — job queue 屬高風險邏輯，
須有測試；docs/ingestion.md 補頁後...手動重建).

The LLM transport is faked exactly like `test_questions_generation.py`
(`httpx2.MockTransport`) so classification/embedding calls never touch the
network — real assertions cover what matters here: old chunks are deleted,
new ones reflect the *current* page markdown, and page rows/markdown are
never touched. No live LLM call, per task instructions.
"""

import json
from collections.abc import Callable

import httpx2
import openai
import pytest
from factories import create_job
from sqlalchemy import select

import backend.ingestion.pipeline as pipeline_module
from backend.core.config import Settings
from backend.db.session import AsyncSessionLocal
from backend.jobs.worker import claim_job, run_claimed_job
from backend.llm.client import LLMClient
from backend.models.chunk import Chunk
from backend.models.document import Document
from backend.models.job import Job
from backend.models.page import Page


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


def _classify_and_embed_handler(
    dim: int,
) -> Callable[[httpx2.Request], httpx2.Response]:
    """Every chat call gets a canned classification; every embeddings call
    gets a zero vector of the right dimension -- enough to drive
    `_run_chunk_phase` end to end without asserting on classification
    content (that's already covered by `test_ingestion_classification.py`)."""

    def handler(request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content)
        if request.url.path == "/v1/embeddings":
            return _embeddings_response(model=body["model"], dim=dim)
        content = {
            "subject": "生物",
            "topic": "光合作用",
            "difficulty": "中等",
            "tags": ["葉綠體"],
        }
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


async def _make_document(status: str = "ready") -> int:
    async with AsyncSessionLocal() as session:
        document = Document(source_type="upload", title="doc", status=status)
        session.add(document)
        await session.commit()
        await session.refresh(document)
        return document.id


async def _make_page(document_id: int, page_no: int, status: str, markdown: str | None) -> int:
    async with AsyncSessionLocal() as session:
        page = Page(document_id=document_id, page_no=page_no, status=status, markdown=markdown)
        session.add(page)
        await session.commit()
        await session.refresh(page)
        return page.id


async def _make_stale_chunk(document_id: int, content: str) -> int:
    async with AsyncSessionLocal() as session:
        chunk = Chunk(document_id=document_id, content=content, category_id=None)
        session.add(chunk)
        await session.commit()
        await session.refresh(chunk)
        return chunk.id


async def _run_job(payload: dict[str, object]) -> int:
    job_id = await create_job("rechunk_document", payload=payload)
    async with AsyncSessionLocal() as session:
        claimed = await claim_job(session)
        assert claimed is not None
        assert claimed.id == job_id
    await run_claimed_job(AsyncSessionLocal, job_id)
    return job_id


async def _get_job(job_id: int) -> Job:
    async with AsyncSessionLocal() as session:
        job = await session.get(Job, job_id)
        assert job is not None
        return job


async def test_rechunk_deletes_old_chunks_and_creates_new_ones_from_current_markdown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dim = Settings().embedding_dim
    document_id = await _make_document()
    await _make_page(document_id, 1, "ready", "# 標題\n新的內容在這裡")
    stale_chunk_id = await _make_stale_chunk(document_id, "舊的、過期的 chunk 內容")

    fake_client = _fake_llm_client(_classify_and_embed_handler(dim))
    monkeypatch.setattr(pipeline_module, "get_llm_client", lambda: fake_client)

    job_id = await _run_job({"document_id": document_id})
    job = await _get_job(job_id)

    assert job.status == "done", job.error

    async with AsyncSessionLocal() as session:
        chunks = (
            (await session.execute(select(Chunk).where(Chunk.document_id == document_id)))
            .scalars()
            .all()
        )
    chunk_ids = {chunk.id for chunk in chunks}
    assert stale_chunk_id not in chunk_ids  # old chunk deleted
    # rebuilt from current markdown, not the stale chunk's old content
    assert any("新的內容在這裡" in chunk.content for chunk in chunks)


async def test_rechunk_never_touches_page_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    dim = Settings().embedding_dim
    document_id = await _make_document()
    page_id = await _make_page(document_id, 1, "ready", "頁面內容不變")

    fake_client = _fake_llm_client(_classify_and_embed_handler(dim))
    monkeypatch.setattr(pipeline_module, "get_llm_client", lambda: fake_client)

    await _run_job({"document_id": document_id})

    async with AsyncSessionLocal() as session:
        page = await session.get(Page, page_id)
        assert page is not None
        assert page.status == "ready"
        assert page.markdown == "頁面內容不變"


async def test_rechunk_ignores_failed_pages_markdown_but_uses_ready_ones(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dim = Settings().embedding_dim
    document_id = await _make_document()
    await _make_page(document_id, 1, "ready", "第一頁內容")
    await _make_page(document_id, 2, "failed", None)

    fake_client = _fake_llm_client(_classify_and_embed_handler(dim))
    monkeypatch.setattr(pipeline_module, "get_llm_client", lambda: fake_client)

    job_id = await _run_job({"document_id": document_id})
    job = await _get_job(job_id)
    assert job.status == "done"

    async with AsyncSessionLocal() as session:
        chunks = (
            (await session.execute(select(Chunk).where(Chunk.document_id == document_id)))
            .scalars()
            .all()
        )
    assert all("第一頁內容" in chunk.content for chunk in chunks)


async def test_rechunk_sets_document_ready_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    dim = Settings().embedding_dim
    document_id = await _make_document(status="failed")
    await _make_page(document_id, 1, "ready", "內容")

    fake_client = _fake_llm_client(_classify_and_embed_handler(dim))
    monkeypatch.setattr(pipeline_module, "get_llm_client", lambda: fake_client)

    await _run_job({"document_id": document_id})

    async with AsyncSessionLocal() as session:
        document = await session.get(Document, document_id)
        assert document is not None
        assert document.status == "ready"


async def test_rechunk_fails_the_job_when_no_page_is_ready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dim = Settings().embedding_dim
    document_id = await _make_document()
    await _make_page(document_id, 1, "failed", None)

    fake_client = _fake_llm_client(_classify_and_embed_handler(dim))
    monkeypatch.setattr(pipeline_module, "get_llm_client", lambda: fake_client)

    job_id = await _run_job({"document_id": document_id})
    job = await _get_job(job_id)

    assert job.status == "failed"
    assert job.error is not None
    assert "no ready page" in job.error


async def test_rechunk_marks_document_failed_and_reraises_when_chunk_phase_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document_id = await _make_document()
    await _make_page(document_id, 1, "ready", "內容")

    def broken_handler(request: httpx2.Request) -> httpx2.Response:
        raise RuntimeError("synthetic transport failure")

    fake_client = _fake_llm_client(broken_handler)
    monkeypatch.setattr(pipeline_module, "get_llm_client", lambda: fake_client)

    job_id = await _run_job({"document_id": document_id})
    job = await _get_job(job_id)

    assert job.status == "failed"
    assert job.error is not None

    async with AsyncSessionLocal() as session:
        document = await session.get(Document, document_id)
        assert document is not None
        assert document.status == "failed"
