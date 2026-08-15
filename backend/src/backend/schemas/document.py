"""Response/request schemas for `/v1/documents`, `/v1/pages`, `/v1/assets`."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, HttpUrl

from backend.schemas.job import JobSummaryOut


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    parent_id: int | None


class ChunkOut(BaseModel):
    id: int
    content: str
    tags: list[str]
    category: CategoryOut | None
    has_embedding: bool


class PageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    page_no: int
    status: str
    markdown: str | None


class DocumentListItemOut(BaseModel):
    id: int
    source_type: str
    title: str
    status: str
    source_url: str | None
    created_at: datetime
    page_count: int
    # The most recent `parse_document` job for this document, if any —
    # lets the UI show/retry a failed ingestion without needing a job id
    # that only ever appeared in the original upload/retry response.
    latest_job: JobSummaryOut | None = None


class DocumentDetailOut(BaseModel):
    id: int
    source_type: str
    title: str
    status: str
    source_url: str | None
    summary: str | None
    created_at: datetime
    pages: list[PageOut]
    chunks: list[ChunkOut]
    latest_job: JobSummaryOut | None = None


class DocumentUploadOut(BaseModel):
    document: DocumentListItemOut
    job_id: int


class UrlUploadIn(BaseModel):
    url: HttpUrl
    title: str | None = None
