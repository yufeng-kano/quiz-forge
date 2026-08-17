"""`questions` — LLM-generated questions, `draft` until approved for export.

`embedding` (docs/question-bank.md 題目向量化與語意搜尋;
docs/decisions/2026-08-17-bank-agent-semantic-selection.md D1) is the
question's own vector, separate from any `chunks.embedding` it was generated
from — one chunk can source many questions of different type/difficulty,
so chunk similarity can't stand in for question similarity. Nullable:
`NULL` means "not yet embedded", picked up by the `embed_questions` job
(`backend.questions.embedding`). Dimension comes from `settings.embedding_dim`
(env `EMBEDDING_DIM`), same setting `chunks.embedding` uses — never a second,
hardcoded dimension.
"""

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import ARRAY, CheckConstraint, DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.config import get_settings
from backend.db.base import Base

settings = get_settings()


class Question(Base):
    __tablename__ = "questions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'approved', 'rejected')", name="ck_questions_status"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    difficulty: Mapped[str | None] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    source_chunk_ids: Mapped[list[int]] = mapped_column(
        ARRAY(Integer), nullable=False, default=list
    )
    embedding: Mapped[list[float] | None] = mapped_column(Vector(settings.embedding_dim))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
