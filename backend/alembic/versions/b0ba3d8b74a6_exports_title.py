"""exports title

Revision ID: b0ba3d8b74a6
Revises: e6177074160c
Create Date: 2026-08-15 23:33:26.536337

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b0ba3d8b74a6"
down_revision: str | Sequence[str] | None = "e6177074160c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema.

    `exports.title` (docs/export.md 卷首：考卷標題) — the exam title printed
    on both papers' headers. Required going forward (`POST /v1/exports` body
    validation), but any export row already in a live database predates this
    field, so the column is added with a temporary `''` server default to
    backfill those rows, then the default is dropped so every export created
    from here on must supply a real title through the API.
    """
    op.add_column(
        "exports", sa.Column("title", sa.String(length=255), nullable=False, server_default="")
    )
    op.alter_column("exports", "title", server_default=None)


def downgrade() -> None:
    """Downgrade schema. Drops `exports.title` — the reverse of `upgrade()`."""
    op.drop_column("exports", "title")
