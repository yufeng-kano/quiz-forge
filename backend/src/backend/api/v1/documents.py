"""`/v1/documents` — upload/URL intake, listing, detail and deletion
(docs/ingestion.md 兩條輸入線).

Both `POST /upload` and `POST /url` only create the `documents` row, save
the raw file (upload only) and enqueue a `parse_document` job — all the
actual parsing happens in the background worker
(`backend.ingestion.pipeline`), per .rule 使用者體驗規則 (長任務一律走背景 job).
"""

import asyncio
import shutil

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import get_settings
from backend.db.session import get_session
from backend.ingestion import storage
from backend.ingestion.kind import UnsupportedUploadError, detect_upload_kind
from backend.models.chunk import Chunk
from backend.models.document import Document
from backend.models.job import Job
from backend.models.page import Page
from backend.schemas.document import (
    CategoryOut,
    ChunkOut,
    DocumentDetailOut,
    DocumentListItemOut,
    DocumentUploadOut,
    PageOut,
    RechunkOut,
    UrlUploadIn,
)
from backend.schemas.job import JobSummaryOut

router = APIRouter(prefix="/documents", tags=["documents"])


def _job_summary(job: Job | None) -> JobSummaryOut | None:
    if job is None:
        return None
    return JobSummaryOut(id=job.id, status=job.status, error=job.error)


def _to_list_item(
    document: Document, page_count: int, latest_job: Job | None = None
) -> DocumentListItemOut:
    return DocumentListItemOut(
        id=document.id,
        source_type=document.source_type,
        title=document.title,
        status=document.status,
        source_url=document.source_url,
        created_at=document.created_at,
        page_count=page_count,
        latest_job=_job_summary(latest_job),
    )


async def _latest_parse_document_jobs_map(
    session: AsyncSession, document_ids: list[int]
) -> dict[int, Job]:
    """The most recent `parse_document` job per document id, keyed by
    `document_id` — one query for as many documents as `GET /v1/documents`
    needs, so the list endpoint stays O(1) queries instead of N+1."""
    if not document_ids:
        return {}
    rows = (
        (
            await session.execute(
                select(Job)
                .where(Job.kind == "parse_document")
                .where(Job.payload["document_id"].as_integer().in_(document_ids))
                .order_by(Job.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    latest: dict[int, Job] = {}
    for job in rows:
        raw_document_id = job.payload.get("document_id")
        if isinstance(raw_document_id, int) and raw_document_id not in latest:
            latest[raw_document_id] = job
    return latest


def _to_chunk_out(chunk: Chunk) -> ChunkOut:
    return ChunkOut(
        id=chunk.id,
        content=chunk.content,
        tags=chunk.tags,
        category=CategoryOut.model_validate(chunk.category) if chunk.category else None,
        has_embedding=chunk.embedding is not None,
    )


async def _enqueue_parse_document(session: AsyncSession, document_id: int) -> Job:
    job = Job(kind="parse_document", payload={"document_id": document_id})
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job


@router.post("/upload", response_model=DocumentUploadOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
) -> DocumentUploadOut:
    """Save an uploaded PDF/image/Word file and enqueue its `parse_document` job."""
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="file has no name")
    try:
        detect_upload_kind(file.filename)
    except UnsupportedUploadError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    document = Document(source_type="upload", title=file.filename, status="pending")
    session.add(document)
    await session.commit()
    await session.refresh(document)

    settings = get_settings()
    dest_path = storage.raw_file_path(settings.data_dir, document.id, file.filename)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    contents = await file.read()
    await asyncio.to_thread(dest_path.write_bytes, contents)

    document.raw_file_path = str(dest_path)
    await session.commit()
    await session.refresh(document)

    job = await _enqueue_parse_document(session, document.id)

    return DocumentUploadOut(
        document=_to_list_item(document, page_count=0, latest_job=job), job_id=job.id
    )


@router.post("/url", response_model=DocumentUploadOut, status_code=status.HTTP_201_CREATED)
async def create_url_document(
    body: UrlUploadIn,
    session: AsyncSession = Depends(get_session),
) -> DocumentUploadOut:
    """Register a URL to scrape and enqueue its `parse_document` job."""
    document = Document(
        source_type="url",
        title=body.title or str(body.url),
        status="pending",
        source_url=str(body.url),
    )
    session.add(document)
    await session.commit()
    await session.refresh(document)

    job = await _enqueue_parse_document(session, document.id)

    return DocumentUploadOut(
        document=_to_list_item(document, page_count=0, latest_job=job), job_id=job.id
    )


@router.get("", response_model=list[DocumentListItemOut])
async def list_documents(
    session: AsyncSession = Depends(get_session),
) -> list[DocumentListItemOut]:
    documents = (
        (await session.execute(select(Document).order_by(Document.created_at.desc())))
        .scalars()
        .all()
    )
    count_rows = await session.execute(
        select(Page.document_id, func.count()).group_by(Page.document_id)
    )
    page_counts: dict[int, int] = {document_id: count for document_id, count in count_rows.all()}
    latest_jobs = await _latest_parse_document_jobs_map(
        session, [document.id for document in documents]
    )
    return [
        _to_list_item(
            document, page_counts.get(document.id, 0), latest_job=latest_jobs.get(document.id)
        )
        for document in documents
    ]


@router.get("/{document_id}", response_model=DocumentDetailOut)
async def get_document(
    document_id: int, session: AsyncSession = Depends(get_session)
) -> DocumentDetailOut:
    document = await session.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="document not found")

    latest_job = (await _latest_parse_document_jobs_map(session, [document_id])).get(document_id)

    pages = (
        (
            await session.execute(
                select(Page).where(Page.document_id == document_id).order_by(Page.page_no)
            )
        )
        .scalars()
        .all()
    )
    chunks = (
        (
            await session.execute(
                select(Chunk).where(Chunk.document_id == document_id).order_by(Chunk.id)
            )
        )
        .scalars()
        .all()
    )

    return DocumentDetailOut(
        id=document.id,
        source_type=document.source_type,
        title=document.title,
        status=document.status,
        source_url=document.source_url,
        summary=document.summary,
        created_at=document.created_at,
        pages=[PageOut.model_validate(page) for page in pages],
        chunks=[_to_chunk_out(chunk) for chunk in chunks],
        latest_job=_job_summary(latest_job),
    )


@router.post(
    "/{document_id}/rechunk", response_model=RechunkOut, status_code=status.HTTP_201_CREATED
)
async def rechunk_document(
    document_id: int, session: AsyncSession = Depends(get_session)
) -> RechunkOut:
    """Enqueue a `rechunk_document` job (docs/ingestion.md 補頁後...手動重
    建). 409 unless the document has at least one `ready` page — with none,
    there is no page markdown to chunk from at all."""
    document = await session.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="document not found")

    ready_page_count = (
        await session.execute(
            select(func.count())
            .select_from(Page)
            .where(Page.document_id == document_id, Page.status == "ready")
        )
    ).scalar_one()
    if ready_page_count == 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"document {document_id} has no ready page to rechunk from",
        )

    job = Job(kind="rechunk_document", payload={"document_id": document_id})
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return RechunkOut(job_id=job.id)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(document_id: int, session: AsyncSession = Depends(get_session)) -> None:
    """Delete a document (DB cascade removes pages/assets/chunks) and its stored files."""
    document = await session.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="document not found")

    settings = get_settings()
    await session.delete(document)
    await session.commit()

    upload_dir = storage.document_upload_dir(settings.data_dir, document_id)
    asset_dir = storage.document_asset_dir(settings.data_dir, document_id)
    await asyncio.to_thread(shutil.rmtree, upload_dir, True)
    await asyncio.to_thread(shutil.rmtree, asset_dir, True)
