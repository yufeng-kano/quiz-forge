"""`conversations` / `conversation_messages` — 題庫選題助手對話紀錄
(docs/question-bank.md 題庫選題助手（對話 agent）；docs/data-model.md;
docs/decisions/2026-08-17-bank-agent-semantic-selection.md D6).

Single-user system: no owner column, any number of conversations, each
deletable independently. `conversation_messages.conversation_id` is
`ON DELETE CASCADE` — deleting a conversation deletes its messages in the
same statement, never leaving orphaned rows.

`proposed_question_ids`/`steps` live only on assistant rows (a user row
always has them empty/`None`) — see `backend.questions.agent.bank_agent_turn`
for how a turn fills them in:

- `proposed_question_ids`: the agent's *proposal*, not a selection. D5 —
  the user must explicitly "加入選取" before any of these ids affect the
  export selection; the agent itself never writes to that store.
- `steps`: a jsonb log of every step the agent actually ran this turn (its
  search filters and hit counts, in order), rendered by the frontend as an
  expandable「查詢過程」so a proposal is never a black box.
"""

from datetime import datetime

from sqlalchemy import ARRAY, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Empty until the first user message is posted (`POST
    # /v1/conversations/{id}/messages` derives it from that message's
    # content, truncated to `settings.conversation_title_max_length`).
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"
    __table_args__ = (
        CheckConstraint("role IN ('user', 'assistant')", name="ck_conversation_messages_role"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    proposed_question_ids: Mapped[list[int]] = mapped_column(
        ARRAY(Integer), nullable=False, default=list
    )
    steps: Mapped[list[object] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
