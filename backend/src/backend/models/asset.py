"""`assets` — figures/charts cropped from a page's full-resolution image."""

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(primary_key=True)
    page_id: Mapped[int] = mapped_column(
        ForeignKey("pages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # [ymin, xmin, ymax, xmax], 0-1000 normalized (Gemini convention) — see docs/ingestion.md
    bbox: Mapped[list[int]] = mapped_column(JSONB, nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    caption: Mapped[str | None] = mapped_column(Text)
