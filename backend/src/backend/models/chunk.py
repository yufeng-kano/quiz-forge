"""`chunks` — chunked document text with classification and embedding.

The embedding column's dimension comes from `settings.embedding_dim`
(env `EMBEDDING_DIM`), never hardcoded — see docs/architecture.md.
"""

from pgvector.sqlalchemy import Vector
from sqlalchemy import ARRAY, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.config import get_settings
from backend.db.base import Base

settings = get_settings()


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"), index=True
    )
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(settings.embedding_dim))
