"""folders

Revision ID: 69237e30207c
Revises: b0ba3d8b74a6
Create Date: 2026-08-16 01:54:37.619201

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "69237e30207c"
down_revision: str | Sequence[str] | None = "b0ba3d8b74a6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema.

    `folders` (docs/data-model.md `folders` — 平面資料夾，不巢狀) plus a
    nullable `documents.folder_id` FK, `ON DELETE SET NULL` so deleting a
    folder unfiles its documents instead of blocking the delete or cascading
    into document rows (docs/ingestion.md 文件管理).
    """
    op.create_table(
        "folders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.add_column("documents", sa.Column("folder_id", sa.Integer(), nullable=True))
    op.create_index("ix_documents_folder_id", "documents", ["folder_id"])
    op.create_foreign_key(
        "fk_documents_folder_id_folders",
        "documents",
        "folders",
        ["folder_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Downgrade schema. Reverses `upgrade()`: drops the FK, its index and
    `documents.folder_id`, then the `folders` table itself."""
    op.drop_constraint("fk_documents_folder_id_folders", "documents", type_="foreignkey")
    op.drop_index("ix_documents_folder_id", table_name="documents")
    op.drop_column("documents", "folder_id")
    op.drop_table("folders")
