"""Request/response schemas for `POST /v1/exports` and `/v1/exports` (docs/export.md)."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from backend.export.paper import SUPPORTED_PAPER_SIZES


class ExportIn(BaseModel):
    """`POST /v1/exports` body — which approved questions, on which paper."""

    question_ids: list[int] = Field(min_length=1)
    paper_size: str

    @field_validator("paper_size")
    @classmethod
    def _paper_size_supported(cls, value: str) -> str:
        if value not in SUPPORTED_PAPER_SIZES:
            raise ValueError(
                f"unsupported paper size {value!r}; supported: {sorted(SUPPORTED_PAPER_SIZES)}"
            )
        return value


class ExportOut(BaseModel):
    job_id: int


class ExportListItemOut(BaseModel):
    """One row of `GET /v1/exports` history."""

    id: int
    paper_size: str
    question_count: int
    created_at: datetime
    questions_available: bool
    answers_available: bool
