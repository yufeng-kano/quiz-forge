"""Request/response schemas for `POST /v1/exports` and `/v1/exports` (docs/export.md)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.export.paper import SUPPORTED_PAPER_SIZES
from backend.questions.schemas import QUESTION_TYPE_MODELS


class HeaderFieldsIn(BaseModel):
    """卷首學生資訊列 + 總分欄 開關 (docs/export.md 表頭選項)，四個布林全部預
    設開啟，維持匯出功能加入前的既有版面。`class` 是 Python 關鍵字，欄位名用
    `class_`，經 alias 對外仍收/送 `class`。"""

    model_config = ConfigDict(populate_by_name=True)

    class_: bool = Field(default=True, alias="class")
    seat: bool = True
    name: bool = True
    score: bool = True


class ExportIn(BaseModel):
    """`POST /v1/exports` body — which approved questions, on which paper,
    under which title, with optional per-question-type scoring and
    per-question overrides, and configurable header fields (docs/export.md
    卷面結構)."""

    question_ids: list[int] = Field(min_length=1)
    paper_size: str
    title: str = Field(min_length=1)
    points: dict[str, int] | None = None
    question_points: dict[int, int] | None = None
    header_fields: HeaderFieldsIn = Field(default_factory=HeaderFieldsIn)

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

    @model_validator(mode="after")
    def _question_points_keys_in_question_ids_and_values_positive(self) -> "ExportIn":
        if self.question_points is None:
            return self
        allowed_ids = set(self.question_ids)
        for question_id, amount in self.question_points.items():
            if question_id not in allowed_ids:
                raise ValueError(
                    f"question_points key {question_id} is not in question_ids {self.question_ids}"
                )
            if amount <= 0:
                raise ValueError(f"question_points value for {question_id} must be positive")
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
