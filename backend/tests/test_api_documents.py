"""`/v1/documents`, `/v1/pages/{id}/retry`, `/v1/assets/{id}` through the real
HTTP app.

The `client` fixture disables the job worker pool (`JOB_WORKER_COUNT=0`), so
these tests exercise the API surface (row creation, file storage, cascading
delete, minimal-unit retry gating) without ever calling the LLM — the
`parse_document`/`parse_page` job handlers themselves are exercised for real
against the live provider in the e2e run (see task report).
"""

import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from backend.core.config import get_settings
from backend.db.session import AsyncSessionLocal
from backend.models.asset import Asset
from backend.models.category import Category
from backend.models.document import Document
from backend.models.folder import Folder
from backend.models.job import Job
from backend.models.page import Page


def _make_pdf_bytes() -> bytes:
    # A minimal syntactically-valid PDF; the upload endpoint only needs to
    # store and enqueue it (the worker is disabled in this fixture), so it
    # never actually gets rendered.
    return (
        b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[]/Count 0>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF"
    )


async def test_upload_pdf_creates_document_and_enqueues_job(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    get_settings.cache_clear()

    response = client.post(
        "/v1/documents/upload",
        files={"file": ("sample.pdf", io.BytesIO(_make_pdf_bytes()), "application/pdf")},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["document"]["source_type"] == "upload"
    assert body["document"]["title"] == "sample.pdf"
    assert body["document"]["status"] == "pending"
    assert body["document"]["page_count"] == 0
    assert isinstance(body["job_id"], int)
    assert body["document"]["latest_job"] == {
        "id": body["job_id"],
        "status": "pending",
        "error": None,
    }

    async with AsyncSessionLocal() as session:
        document = await session.get(Document, body["document"]["id"])
        assert document is not None
        assert document.raw_file_path is not None
        assert Path(document.raw_file_path).read_bytes() == _make_pdf_bytes()

        job = await session.get(Job, body["job_id"])
        assert job is not None
        assert job.kind == "parse_document"
        assert job.payload == {"document_id": document.id}
        assert job.status == "pending"

    get_settings.cache_clear()


def test_upload_rejects_unsupported_extension(client: TestClient) -> None:
    response = client.post(
        "/v1/documents/upload",
        files={"file": ("archive.zip", io.BytesIO(b"not a real archive"), "application/zip")},
    )
    assert response.status_code == 400


async def test_create_url_document_enqueues_job(client: TestClient) -> None:
    response = client.post(
        "/v1/documents/url",
        json={"url": "https://zh.wikipedia.org/wiki/Photosynthesis", "title": "光合作用"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["document"]["source_type"] == "url"
    assert body["document"]["status"] == "pending"
    assert body["document"]["title"] == "光合作用"

    async with AsyncSessionLocal() as session:
        document = await session.get(Document, body["document"]["id"])
        assert document is not None
        assert document.source_url == "https://zh.wikipedia.org/wiki/Photosynthesis"
        assert document.raw_file_path is None


async def test_list_documents_reports_status_and_page_counts(client: TestClient) -> None:
    async with AsyncSessionLocal() as session:
        document = Document(source_type="upload", title="doc-a", status="ready")
        session.add(document)
        await session.commit()
        await session.refresh(document)
        session.add(Page(document_id=document.id, page_no=1, status="ready", markdown="p1"))
        session.add(Page(document_id=document.id, page_no=2, status="failed"))
        await session.commit()

    response = client.get("/v1/documents")
    assert response.status_code == 200
    items = {item["id"]: item for item in response.json()}
    assert items[document.id]["status"] == "ready"
    assert items[document.id]["page_count"] == 2
    assert items[document.id]["latest_job"] is None
    assert items[document.id]["folder_id"] is None


# ---------------------------------------------------------------------------
# GET /v1/documents -- folder_id / unfiled filter (docs/ingestion.md 文件管理)
# ---------------------------------------------------------------------------


async def _make_folder(name: str) -> int:
    async with AsyncSessionLocal() as session:
        folder = Folder(name=name)
        session.add(folder)
        await session.commit()
        await session.refresh(folder)
        return folder.id


async def test_list_documents_filters_by_folder_id(client: TestClient) -> None:
    folder_id = await _make_folder("教材")
    async with AsyncSessionLocal() as session:
        filed = Document(source_type="upload", title="filed", status="ready", folder_id=folder_id)
        unfiled = Document(source_type="upload", title="unfiled", status="ready")
        session.add_all([filed, unfiled])
        await session.commit()
        await session.refresh(filed)
        await session.refresh(unfiled)

    response = client.get("/v1/documents", params={"folder_id": folder_id})
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()}
    assert ids == {filed.id}


async def test_list_documents_filters_unfiled(client: TestClient) -> None:
    folder_id = await _make_folder("教材")
    async with AsyncSessionLocal() as session:
        filed = Document(source_type="upload", title="filed", status="ready", folder_id=folder_id)
        unfiled = Document(source_type="upload", title="unfiled", status="ready")
        session.add_all([filed, unfiled])
        await session.commit()
        await session.refresh(filed)
        await session.refresh(unfiled)

    response = client.get("/v1/documents", params={"unfiled": "true"})
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()}
    assert ids == {unfiled.id}


def test_list_documents_rejects_folder_id_and_unfiled_together(client: TestClient) -> None:
    response = client.get("/v1/documents", params={"folder_id": 1, "unfiled": "true"})
    assert response.status_code == 422


async def test_list_and_detail_expose_latest_parse_document_job(client: TestClient) -> None:
    async with AsyncSessionLocal() as session:
        document = Document(source_type="upload", title="doc-g", status="failed")
        session.add(document)
        await session.commit()
        await session.refresh(document)

        # An older, already-superseded job for the same document, plus the
        # current (failed) one -- the endpoint must surface the latter.
        session.add(Job(kind="parse_document", payload={"document_id": document.id}, status="done"))
        await session.commit()
        stale_job = (await session.execute(select(Job))).scalars().first()
        assert stale_job is not None
        await session.execute(
            text("UPDATE jobs SET created_at = created_at - interval '1 hour' WHERE id = :id"),
            {"id": stale_job.id},
        )
        latest_job = Job(
            kind="parse_document",
            payload={"document_id": document.id},
            status="failed",
            error="vision call timed out",
        )
        session.add(latest_job)
        await session.commit()
        await session.refresh(latest_job)

    list_response = client.get("/v1/documents")
    list_item = next(item for item in list_response.json() if item["id"] == document.id)
    assert list_item["latest_job"] == {
        "id": latest_job.id,
        "status": "failed",
        "error": "vision call timed out",
    }

    detail_response = client.get(f"/v1/documents/{document.id}")
    assert detail_response.json()["latest_job"] == {
        "id": latest_job.id,
        "status": "failed",
        "error": "vision call timed out",
    }


async def test_get_document_detail_includes_pages_and_chunks(client: TestClient) -> None:
    from backend.ingestion.classification import get_or_create_category
    from backend.models.chunk import Chunk

    async with AsyncSessionLocal() as session:
        document = Document(source_type="upload", title="doc-b", status="ready")
        session.add(document)
        await session.commit()
        await session.refresh(document)

        session.add(
            Page(document_id=document.id, page_no=1, status="ready", markdown="# 標題\n內容")
        )
        await session.commit()

        subject = await get_or_create_category(session, "生物", parent_id=None)
        topic = await get_or_create_category(session, "光合作用", parent_id=subject.id)
        session.add(
            Chunk(
                document_id=document.id,
                content="# 標題\n內容",
                category_id=topic.id,
                tags=["葉綠體", "難度:中等"],
                embedding=None,
            )
        )
        await session.commit()

    response = client.get(f"/v1/documents/{document.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == document.id
    assert body["folder_id"] is None
    assert len(body["pages"]) == 1
    assert body["pages"][0]["markdown"] == "# 標題\n內容"
    assert len(body["chunks"]) == 1
    chunk = body["chunks"][0]
    assert chunk["tags"] == ["葉綠體", "難度:中等"]
    assert chunk["category"]["name"] == "光合作用"
    assert chunk["has_embedding"] is False


def test_get_document_404_for_missing_document(client: TestClient) -> None:
    response = client.get("/v1/documents/999999999")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /v1/documents/{id} -- rename / move to a folder (docs/ingestion.md 文件管理)
# ---------------------------------------------------------------------------


async def _make_document(title: str = "doc", folder_id: int | None = None) -> int:
    async with AsyncSessionLocal() as session:
        document = Document(
            source_type="upload", title=title, status="ready", folder_id=folder_id
        )
        session.add(document)
        await session.commit()
        await session.refresh(document)
        return document.id


async def test_patch_document_renames_and_returns_document_detail_shape(
    client: TestClient,
) -> None:
    document_id = await _make_document("舊標題")

    response = client.patch(f"/v1/documents/{document_id}", json={"title": "新標題"})

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "新標題"
    # Same shape GET /v1/documents/{id} returns.
    assert set(body.keys()) == {
        "id",
        "source_type",
        "title",
        "status",
        "source_url",
        "summary",
        "folder_id",
        "created_at",
        "pages",
        "chunks",
        "latest_job",
    }

    async with AsyncSessionLocal() as session:
        document = await session.get(Document, document_id)
        assert document is not None
        assert document.title == "新標題"


async def test_patch_document_strips_whitespace_from_title(client: TestClient) -> None:
    document_id = await _make_document("舊標題")

    response = client.patch(f"/v1/documents/{document_id}", json={"title": "  新標題  "})

    assert response.status_code == 200
    assert response.json()["title"] == "新標題"


async def test_patch_document_rejects_blank_title(client: TestClient) -> None:
    document_id = await _make_document("舊標題")

    response = client.patch(f"/v1/documents/{document_id}", json={"title": "   "})

    assert response.status_code == 422
    async with AsyncSessionLocal() as session:
        document = await session.get(Document, document_id)
        assert document is not None
        assert document.title == "舊標題"  # untouched


def test_patch_document_rejects_null_title(client: TestClient) -> None:
    response = client.patch("/v1/documents/1", json={"title": None})
    assert response.status_code == 422


async def test_patch_document_rejects_title_over_max_length(client: TestClient) -> None:
    document_id = await _make_document("舊標題")
    settings = get_settings()

    too_long_title = "A" * (settings.webpage_title_max_length + 1)
    response = client.patch(f"/v1/documents/{document_id}", json={"title": too_long_title})

    assert response.status_code == 422


def test_patch_document_404_for_missing_document(client: TestClient) -> None:
    response = client.patch("/v1/documents/999999999", json={"title": "新標題"})
    assert response.status_code == 404


async def test_patch_document_moves_to_folder(client: TestClient) -> None:
    document_id = await _make_document("doc")
    folder_id = await _make_folder("教材")

    response = client.patch(f"/v1/documents/{document_id}", json={"folder_id": folder_id})

    assert response.status_code == 200
    assert response.json()["folder_id"] == folder_id
    async with AsyncSessionLocal() as session:
        document = await session.get(Document, document_id)
        assert document is not None
        assert document.folder_id == folder_id


async def test_patch_document_unfiles_with_explicit_null_folder_id(client: TestClient) -> None:
    folder_id = await _make_folder("教材")
    document_id = await _make_document("doc", folder_id=folder_id)

    response = client.patch(f"/v1/documents/{document_id}", json={"folder_id": None})

    assert response.status_code == 200
    assert response.json()["folder_id"] is None
    async with AsyncSessionLocal() as session:
        document = await session.get(Document, document_id)
        assert document is not None
        assert document.folder_id is None


async def test_patch_document_omitted_folder_id_leaves_it_untouched(client: TestClient) -> None:
    folder_id = await _make_folder("教材")
    document_id = await _make_document("舊標題", folder_id=folder_id)

    response = client.patch(f"/v1/documents/{document_id}", json={"title": "新標題"})

    assert response.status_code == 200
    assert response.json()["folder_id"] == folder_id


async def test_patch_document_404_for_unknown_folder_id(client: TestClient) -> None:
    document_id = await _make_document("doc")

    response = client.patch(f"/v1/documents/{document_id}", json={"folder_id": 999999999})

    assert response.status_code == 404
    async with AsyncSessionLocal() as session:
        document = await session.get(Document, document_id)
        assert document is not None
        assert document.folder_id is None  # untouched


async def test_delete_document_removes_row_and_files(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    get_settings.cache_clear()

    upload_response = client.post(
        "/v1/documents/upload",
        files={"file": ("sample.pdf", io.BytesIO(_make_pdf_bytes()), "application/pdf")},
    )
    document_id = upload_response.json()["document"]["id"]

    async with AsyncSessionLocal() as session:
        document = await session.get(Document, document_id)
        assert document is not None
        assert document.raw_file_path is not None
        raw_path = Path(document.raw_file_path)
    assert raw_path.exists()

    delete_response = client.delete(f"/v1/documents/{document_id}")
    assert delete_response.status_code == 204

    assert not raw_path.exists()
    async with AsyncSessionLocal() as session:
        assert await session.get(Document, document_id) is None

    get_settings.cache_clear()


async def test_delete_document_runs_category_gc_and_preserves_shared_categories(
    client: TestClient,
) -> None:
    """docs/ingestion.md 文件刪除 — end-to-end through the real DELETE
    endpoint: an orphaned topic is collected, a topic shared with another
    document's chunk survives (and so does its subject, which still has
    that surviving child), and once the second document is deleted too the
    now fully-unreferenced, childless subject/topic pair is collected."""
    from backend.ingestion.classification import get_or_create_category
    from backend.models.chunk import Chunk

    async with AsyncSessionLocal() as session:
        doc_a = Document(source_type="upload", title="doc-a", status="ready")
        doc_b = Document(source_type="upload", title="doc-b", status="ready")
        session.add_all([doc_a, doc_b])
        await session.commit()
        await session.refresh(doc_a)
        await session.refresh(doc_b)

        subject = await get_or_create_category(session, "生物", parent_id=None)
        shared_topic = await get_or_create_category(session, "光合作用", parent_id=subject.id)
        doc_a_only_topic = await get_or_create_category(session, "呼吸作用", parent_id=subject.id)

        session.add_all(
            [
                Chunk(document_id=doc_a.id, content="A 內容 1", category_id=shared_topic.id),
                Chunk(document_id=doc_a.id, content="A 內容 2", category_id=doc_a_only_topic.id),
                Chunk(document_id=doc_b.id, content="B 內容", category_id=shared_topic.id),
            ]
        )
        await session.commit()

    delete_a_response = client.delete(f"/v1/documents/{doc_a.id}")
    assert delete_a_response.status_code == 204

    async with AsyncSessionLocal() as session:
        remaining_ids = {c.id for c in (await session.execute(select(Category))).scalars().all()}
    # doc_a's own topic is now unreferenced -> collected.
    assert doc_a_only_topic.id not in remaining_ids
    # still referenced by doc_b's chunk -> survives, and so does its subject.
    assert shared_topic.id in remaining_ids
    assert subject.id in remaining_ids

    delete_b_response = client.delete(f"/v1/documents/{doc_b.id}")
    assert delete_b_response.status_code == 204

    async with AsyncSessionLocal() as session:
        remaining_ids = {c.id for c in (await session.execute(select(Category))).scalars().all()}
    assert shared_topic.id not in remaining_ids
    assert subject.id not in remaining_ids


async def test_delete_document_does_not_touch_questions_with_dangling_source_chunk_ids(
    client: TestClient,
) -> None:
    """docs/ingestion.md 文件刪除 — questions are a separate, already-
    approved artifact; deleting a document must leave them exactly as they
    were, `source_chunk_ids` pointing at now-gone chunk ids included."""
    from backend.models.chunk import Chunk
    from backend.models.question import Question

    async with AsyncSessionLocal() as session:
        document = Document(source_type="upload", title="doc-q", status="ready")
        session.add(document)
        await session.commit()
        await session.refresh(document)

        chunk = Chunk(document_id=document.id, content="內容", category_id=None)
        session.add(chunk)
        await session.commit()
        await session.refresh(chunk)

        question = Question(
            type="single_choice",
            status="approved",
            payload={"stem": "題幹", "options": ["A", "B"], "answer": "A"},
            source_chunk_ids=[chunk.id],
        )
        session.add(question)
        await session.commit()
        await session.refresh(question)
        question_id = question.id

    response = client.delete(f"/v1/documents/{document.id}")
    assert response.status_code == 204

    async with AsyncSessionLocal() as session:
        kept_question = await session.get(Question, question_id)
        assert kept_question is not None
        assert kept_question.source_chunk_ids == [chunk.id]
        assert await session.get(Chunk, chunk.id) is None


async def test_rechunk_enqueues_job_when_a_ready_page_exists(client: TestClient) -> None:
    async with AsyncSessionLocal() as session:
        document = Document(source_type="upload", title="doc-h", status="ready")
        session.add(document)
        await session.commit()
        await session.refresh(document)
        session.add(Page(document_id=document.id, page_no=1, status="ready", markdown="內容"))
        await session.commit()

    response = client.post(f"/v1/documents/{document.id}/rechunk")

    assert response.status_code == 201
    body = response.json()
    assert isinstance(body["job_id"], int)

    async with AsyncSessionLocal() as session:
        job = await session.get(Job, body["job_id"])
        assert job is not None
        assert job.kind == "rechunk_document"
        assert job.payload == {"document_id": document.id}
        assert job.status == "pending"


async def test_rechunk_409_when_no_page_is_ready(client: TestClient) -> None:
    async with AsyncSessionLocal() as session:
        document = Document(source_type="upload", title="doc-i", status="failed")
        session.add(document)
        await session.commit()
        await session.refresh(document)
        session.add(Page(document_id=document.id, page_no=1, status="failed"))
        await session.commit()

    response = client.post(f"/v1/documents/{document.id}/rechunk")
    assert response.status_code == 409


async def test_rechunk_409_when_document_has_no_pages_at_all(client: TestClient) -> None:
    async with AsyncSessionLocal() as session:
        document = Document(source_type="upload", title="doc-j", status="pending")
        session.add(document)
        await session.commit()
        await session.refresh(document)

    response = client.post(f"/v1/documents/{document.id}/rechunk")
    assert response.status_code == 409


def test_rechunk_404_for_missing_document(client: TestClient) -> None:
    response = client.post("/v1/documents/999999999/rechunk")
    assert response.status_code == 404


async def test_retry_page_rejects_page_still_processing(client: TestClient) -> None:
    async with AsyncSessionLocal() as session:
        document = Document(source_type="upload", title="doc-c", status="processing")
        session.add(document)
        await session.commit()
        await session.refresh(document)
        page = Page(document_id=document.id, page_no=1, status="processing")
        session.add(page)
        await session.commit()
        await session.refresh(page)

    response = client.post(f"/v1/pages/{page.id}/retry")
    assert response.status_code == 409


async def test_retry_page_enqueues_parse_page_job_for_failed_page(client: TestClient) -> None:
    async with AsyncSessionLocal() as session:
        document = Document(source_type="upload", title="doc-d", status="ready")
        session.add(document)
        await session.commit()
        await session.refresh(document)
        page = Page(document_id=document.id, page_no=1, status="failed")
        session.add(page)
        await session.commit()
        await session.refresh(page)

    response = client.post(f"/v1/pages/{page.id}/retry")
    assert response.status_code == 201
    body = response.json()
    assert body["kind"] == "parse_page"
    assert body["status"] == "pending"

    async with AsyncSessionLocal() as session:
        job = await session.get(Job, body["id"])
        assert job is not None
        assert job.payload == {"page_id": page.id}


def test_retry_page_404_for_missing_page(client: TestClient) -> None:
    response = client.post("/v1/pages/999999999/retry")
    assert response.status_code == 404


async def test_get_asset_serves_file_with_png_content_type(
    client: TestClient, tmp_path: Path
) -> None:
    async with AsyncSessionLocal() as session:
        document = Document(source_type="upload", title="doc-e", status="ready")
        session.add(document)
        await session.commit()
        await session.refresh(document)
        page = Page(document_id=document.id, page_no=1, status="ready")
        session.add(page)
        await session.commit()
        await session.refresh(page)

        asset_path = tmp_path / "cropped.png"
        asset_path.write_bytes(b"\x89PNG-fake-bytes")
        asset = Asset(page_id=page.id, bbox=[0, 0, 100, 100], file_path=str(asset_path))
        session.add(asset)
        await session.commit()
        await session.refresh(asset)

    response = client.get(f"/v1/assets/{asset.id}")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content == b"\x89PNG-fake-bytes"


async def test_get_asset_404_when_file_missing_on_disk(client: TestClient) -> None:
    async with AsyncSessionLocal() as session:
        document = Document(source_type="upload", title="doc-f", status="ready")
        session.add(document)
        await session.commit()
        await session.refresh(document)
        page = Page(document_id=document.id, page_no=1, status="ready")
        session.add(page)
        await session.commit()
        await session.refresh(page)

        asset = Asset(
            page_id=page.id, bbox=[0, 0, 100, 100], file_path="/nonexistent/path/fig.png"
        )
        session.add(asset)
        await session.commit()
        await session.refresh(asset)

    response = client.get(f"/v1/assets/{asset.id}")
    assert response.status_code == 404


def test_get_asset_404_for_missing_asset(client: TestClient) -> None:
    response = client.get("/v1/assets/999999999")
    assert response.status_code == 404
