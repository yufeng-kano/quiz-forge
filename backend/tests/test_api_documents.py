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
from backend.models.document import Document
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
