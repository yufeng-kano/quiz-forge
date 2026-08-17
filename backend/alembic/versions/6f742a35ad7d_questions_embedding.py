"""questions embedding

Revision ID: 6f742a35ad7d
Revises: 69237e30207c
Create Date: 2026-08-17 08:40:54.390551

"""

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op
from backend.core.config import get_settings

# revision identifiers, used by Alembic.
revision: str = "6f742a35ad7d"
down_revision: str | Sequence[str] | None = "69237e30207c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema.

    `questions.embedding` (docs/question-bank.md 題目向量化與語意搜尋;
    docs/decisions/2026-08-17-bank-agent-semantic-selection.md D1) — nullable
    `vector(EMBEDDING_DIM)`, same dimension setting `chunks.embedding`
    already uses. `NULL` means "not yet embedded"; every question inserted
    before this migration existing is exactly that state, backfilled later
    by the `embed_questions` job rather than by this migration itself. The
    `vector` extension already exists (created by the initial migration), so
    no `CREATE EXTENSION` is needed here.
    """
    embedding_dim = get_settings().embedding_dim
    op.add_column("questions", sa.Column("embedding", Vector(embedding_dim), nullable=True))


def downgrade() -> None:
    """Downgrade schema. Drops `questions.embedding` — the reverse of `upgrade()`."""
    op.drop_column("questions", "embedding")
