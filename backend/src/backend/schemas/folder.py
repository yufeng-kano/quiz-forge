"""Response/request schemas for `/v1/folders` (docs/ingestion.md 文件管理；
docs/data-model.md `folders` — 平面資料夾)."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class FolderOut(BaseModel):
    id: int
    name: str
    created_at: datetime
    document_count: int


class FolderIn(BaseModel):
    """`POST /v1/folders` (create) / `PATCH /v1/folders/{id}` (rename) body —
    name required, stripped, non-blank (docs/ingestion.md `GET/POST
    /api/v1/folders`、`PATCH /api/v1/folders/{id}`（改名）). Uniqueness is
    enforced case-sensitively at the call site (409 on duplicate), not here."""

    name: str = Field(min_length=1)

    @field_validator("name")
    @classmethod
    def _name_not_blank_after_strip(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("name must not be blank")
        return stripped
