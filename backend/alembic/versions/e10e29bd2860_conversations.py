"""conversations

Revision ID: e10e29bd2860
Revises: 6f742a35ad7d
Create Date: 2026-08-17 08:59:47.416137

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e10e29bd2860"
down_revision: str | Sequence[str] | None = "6f742a35ad7d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema.

    `conversations` / `conversation_messages` (docs/question-bank.md 題庫選題
    助手（對話 agent）；docs/data-model.md; docs/decisions/
    2026-08-17-bank-agent-semantic-selection.md D6) — single-user system, no
    owner column. `conversation_messages.conversation_id` is `ON DELETE
    CASCADE`: deleting a conversation deletes its messages in the same
    statement. `role` is constrained to `user`/`assistant` by a CHECK, same
    pattern as `questions.status`'s `ck_questions_status`.
    """
    op.create_table(
        "conversations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=255), nullable=False, server_default=""),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_table(
        "conversation_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "proposed_question_ids",
            postgresql.ARRAY(sa.Integer()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column("steps", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["conversations.id"], ondelete="CASCADE"
        ),
        sa.CheckConstraint(
            "role IN ('user', 'assistant')", name="ck_conversation_messages_role"
        ),
    )
    op.create_index(
        "ix_conversation_messages_conversation_id",
        "conversation_messages",
        ["conversation_id"],
    )


def downgrade() -> None:
    """Downgrade schema. Reverses `upgrade()`: drops `conversation_messages`
    (and its index) before `conversations`, since the former FKs to the
    latter."""
    op.drop_index(
        "ix_conversation_messages_conversation_id", table_name="conversation_messages"
    )
    op.drop_table("conversation_messages")
    op.drop_table("conversations")
