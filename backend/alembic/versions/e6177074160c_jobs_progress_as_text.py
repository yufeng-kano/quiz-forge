"""jobs progress as text

Revision ID: e6177074160c
Revises: 51e2e5d860a8
Create Date: 2026-08-15 21:00:43.811157

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e6177074160c"
down_revision: str | Sequence[str] | None = "51e2e5d860a8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema.

    `jobs.progress` moves from an integer percentage to a free-form display
    string (e.g. "12/40" pages, per docs/architecture.md) so multi-page /
    multi-question jobs can report progress in the unit the user sees.
    """
    op.alter_column(
        "jobs",
        "progress",
        existing_type=sa.Integer(),
        type_=sa.String(length=50),
        nullable=False,
        server_default=sa.text("''"),
        postgresql_using="progress::text",
    )


def downgrade() -> None:
    """Downgrade schema.

    Reverses to an integer column. Any progress value that isn't a bare
    integer string (e.g. "12/40") cannot be losslessly represented as an
    integer percentage again, so it is reset to 0 rather than failing the
    cast outright.

    The text default (`''`) has no automatic cast to integer, so it must be
    dropped before the type change and re-added as `0` afterward — a single
    combined `ALTER COLUMN ... TYPE ... USING ...` fails with
    `DatatypeMismatchError` while the incompatible default is still in place.
    """
    op.alter_column("jobs", "progress", server_default=None)
    op.alter_column(
        "jobs",
        "progress",
        existing_type=sa.String(length=50),
        type_=sa.Integer(),
        nullable=False,
        postgresql_using="(CASE WHEN progress ~ '^[0-9]+$' THEN progress::integer ELSE 0 END)",
    )
    op.alter_column("jobs", "progress", existing_type=sa.Integer(), server_default="0")
