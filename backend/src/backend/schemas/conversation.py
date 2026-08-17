"""Request/response schemas for `/v1/conversations` (docs/question-bank.md
題庫選題助手（對話 agent）相關 API)."""

from datetime import datetime

from pydantic import BaseModel, Field


class ConversationMessageOut(BaseModel):
    id: int
    role: str
    content: str
    proposed_question_ids: list[int]
    steps: list[object] | None
    created_at: datetime


class ConversationOut(BaseModel):
    """`GET /v1/conversations` list item — no messages, just enough to
    render a conversation list (title, last-updated)."""

    id: int
    title: str
    created_at: datetime
    updated_at: datetime


class ConversationDetailOut(ConversationOut):
    """`GET /v1/conversations/{id}` — same envelope plus every message in
    the conversation, oldest first."""

    messages: list[ConversationMessageOut]


class ConversationMessageIn(BaseModel):
    """`POST /v1/conversations/{id}/messages` body — the user's new message
    plus whatever question ids are currently selected on screen
    (`selected_question_ids`), fed into the agent's prompt as context but
    never written to by the agent itself (D5)."""

    content: str = Field(min_length=1)
    selected_question_ids: list[int] = Field(default_factory=list)


class PostMessageOut(BaseModel):
    job_id: int
    message_id: int
