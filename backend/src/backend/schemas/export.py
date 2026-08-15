"""Request/response schemas for `POST /v1/exports` and `/v1/exports` (docs/export.md)."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from backend.export.paper import SUPPORTED_PAPER_SIZES
from backend.questions.schemas import QUESTION_TYPE_MODELS


class ExportIn(BaseModel):
    """`POST /v1/exports` body — which approved questions, on which paper,
    under which title, with optional per-question-type scoring
    (docs/export.md 卷面結構)."""

    question_ids: list[int] = Field(min_length=1)
    paper_size: str
    title: str = Field(min_length=1)
    points: dict[str, int] | None = None

    @field_validator("paper_size")
    @classmethod
    def _paper_size_supported(cls, value: str) -> str:
        if value not in SUPPORTED_PAPER_SIZES:
            raise ValueError(
                f"unsupported paper size {value!r}; supported: {sorted(SUPPORTED_PAPER_SIZES)}"
            )
        return value

    @field_validator("title")
    @classmethod
    def _title_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("title must not be blank")
        return value

    @model_validator(mode="after")
    def _points_keys_are_known_types_and_values_positive(self) -> "ExportIn":
        if self.points is None:
            return self
        for question_type, amount in self.points.items():
            if question_type not in QUESTION_TYPE_MODELS:
                raise ValueError(f"points key {question_type!r} is not a known question type")
            if amount <= 0:
                raise ValueError(f"points value for {question_type!r} must be positive")
        return self


class ExportOut(BaseModel):
    job_id: int


class ExportListItemOut(BaseModel):
    """One row of `GET /v1/exports` history."""

    id: int
    title: str
    paper_size: str
    question_count: int
    created_at: datetime
    questions_available: bool
    answers_available: bool
