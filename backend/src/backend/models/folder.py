"""`folders` — flat (not nested) user-managed grouping for the document
library (docs/data-model.md 平面資料夾；docs/ingestion.md 文件管理).

Unrelated to `categories` (LLM knowledge classification, driving question
generation scope): folders only affect how a user browses/organizes the
document library."""

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base


class Folder(Base):
    __tablename__ = "folders"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
