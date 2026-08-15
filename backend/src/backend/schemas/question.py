"""Request/response schemas for `POST /v1/generate` and `/v1/questions`."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from backend.questions.schemas import QuestionType


class GenerateItemIn(BaseModel):
    """One `POST /v1/generate` `items[]` entry — a question type and how many
    of it to draft (docs/question-bank.md 出題流程 step 1 — 多個「題型 × 數量」
    項目，一個 job 出完)."""

    question_type: QuestionType
    count: int = Field(gt=0)


class GenerateIn(BaseModel):
    """`POST /v1/generate` body — scope, shared difficulty, and one or more
    `{question_type, count}` combos generated together by a single job."""

    document_ids: list[int] | None = None
    category_ids: list[int] | None = None
    items: list[GenerateItemIn] = Field(min_length=1)
    difficulty: str | None = None

    @model_validator(mode="after")
    def _scope_not_empty(self) -> "GenerateIn":
        if not self.document_ids and not self.category_ids:
            raise ValueError("at least one of document_ids or category_ids must be given")
        return self

    @model_validator(mode="after")
    def _items_no_duplicate_question_type(self) -> "GenerateIn":
        types = [item.question_type for item in self.items]
        if len(types) != len(set(types)):
            raise ValueError("items must not repeat the same question_type more than once")
        return self


class GenerateOut(BaseModel):
    job_id: int


class QuestionListItemOut(BaseModel):
    id: int
    type: str
    difficulty: str | None
    status: str
    payload: dict[str, object]
    source_chunk_ids: list[int]
    created_at: datetime


class QuestionListOut(BaseModel):
    """`GET /v1/questions` pagination envelope (docs/question-bank.md
    limit/offset 分頁封包)."""

    items: list[QuestionListItemOut]
    total: int
    limit: int
    offset: int


class QuestionCreateIn(BaseModel):
    """`POST /v1/questions` body — manual question authoring
    (docs/question-bank.md 手動建題). Defaults to `approved` (老師自己寫的
    不需審); `source_chunk_ids` is always empty (see the handler, not
    settable here — a hand-written question has no LLM source chunk)."""

    type: QuestionType
    difficulty: str | None = None
    payload: dict[str, object]
    status: Literal["draft", "approved"] = "approved"


class SourceChunkOut(BaseModel):
    id: int
    content: str


class QuestionDetailOut(QuestionListItemOut):
    source_chunks: list[SourceChunkOut]


class QuestionPatchIn(BaseModel):
    """`PATCH /v1/questions/{id}` body — both fields optional, either or both
    may be sent; only the ones actually present in the request are applied
    (see `model_fields_set` usage in the handler)."""

    payload: dict[str, object] | None = None
    difficulty: str | None = None
