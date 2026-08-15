"""Response/request schemas for `/v1/documents`, `/v1/pages`, `/v1/assets`."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from backend.core.config import get_settings
from backend.schemas.job import JobSummaryOut


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    parent_id: int | None


class CategoryPatchIn(BaseModel):
    """`PATCH /v1/categories/{id}` body — rename only (docs/question-bank.md
    改名；不做合併)."""

    name: str = Field(min_length=1)

    @field_validator("name")
    @classmethod
    def _name_not_blank_after_strip(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("name must not be blank")
        return stripped


class RechunkOut(BaseModel):
    """`POST /v1/documents/{id}/rechunk` response (docs/ingestion.md 補頁後
    用...手動重建)."""

    job_id: int


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
    folder_id: int | None
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
    folder_id: int | None
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


class DocumentPatchIn(BaseModel):
    """`PATCH /v1/documents/{id}` body (docs/ingestion.md 文件管理) — a
    partial update: any subset of `title`/`folder_id` may be given.

    `folder_id` is legitimately nullable (`null` means "move to unfiled"), so
    "field omitted" vs. "field explicitly null" has to be told apart via
    `model_fields_set` at the call site — the field's own default can't
    carry that distinction. `title` has no such nullable meaning (the DB
    column is `NOT NULL`), so an explicit `null` for it is rejected by the
    validator below outright; the validator never runs for an *omitted*
    title at all (pydantic skips validating the field's own default unless
    `validate_default=True`, which this model does not set), so it only ever
    sees a value the client actually sent.
    """

    title: str | None = None
    folder_id: int | None = None

    @field_validator("title")
    @classmethod
    def _title_valid(cls, value: str | None) -> str | None:
        if value is None:
            raise ValueError("title must not be null")
        stripped = value.strip()
        if not stripped:
            raise ValueError("title must not be blank")
        max_length = get_settings().webpage_title_max_length
        if len(stripped) > max_length:
            raise ValueError(f"title must be at most {max_length} characters")
        return stripped
