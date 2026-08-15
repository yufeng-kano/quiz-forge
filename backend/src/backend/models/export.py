"""`exports` — generated Word exam papers (question sheet + answer sheet)."""

from datetime import datetime

from sqlalchemy import ARRAY, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base


class Export(Base):
    __tablename__ = "exports"

    id: Mapped[int] = mapped_column(primary_key=True)
    paper_size: Mapped[str] = mapped_column(String(20), nullable=False)
    question_ids: Mapped[list[int]] = mapped_column(ARRAY(Integer), nullable=False, default=list)
    docx_path: Mapped[str | None] = mapped_column(String(1024))
    answer_docx_path: Mapped[str | None] = mapped_column(String(1024))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
