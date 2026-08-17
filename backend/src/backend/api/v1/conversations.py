"""`/v1/conversations` — 題庫選題助手對話 CRUD 與訊息送出
(docs/question-bank.md 題庫選題助手（對話 agent）相關 API; docs/decisions/
2026-08-17-bank-agent-semantic-selection.md D6).

Every turn's actual LLM work happens in the background
(`backend.questions.agent.bank_agent_turn`, job kind `bank_agent_turn`) — per
.rule 使用者體驗規則 (長任務一律走背景 job，前端輪詢 `/api/v1/jobs/{id}`),
`POST .../messages` only ever stores the user's message and enqueues the
job; it never calls the LLM inline.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import get_settings
from backend.db.session import get_session
from backend.models.conversation import Conversation, ConversationMessage
from backend.models.job import Job
from backend.schemas.conversation import (
    ConversationDetailOut,
    ConversationMessageIn,
    ConversationMessageOut,
    ConversationOut,
    PostMessageOut,
)

router = APIRouter(prefix="/conversations", tags=["conversations"])


def _to_message_out(message: ConversationMessage) -> ConversationMessageOut:
    return ConversationMessageOut(
        id=message.id,
        role=message.role,
        content=message.content,
        proposed_question_ids=message.proposed_question_ids,
        steps=message.steps,
        created_at=message.created_at,
    )


def _to_conversation_out(conversation: Conversation) -> ConversationOut:
    return ConversationOut(
        id=conversation.id,
        title=conversation.title,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
    )


async def _get_conversation_or_404(conversation_id: int, session: AsyncSession) -> Conversation:
    conversation = await session.get(Conversation, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="conversation not found")
    return conversation


@router.get("", response_model=list[ConversationOut])
async def list_conversations(
    session: AsyncSession = Depends(get_session),
) -> list[ConversationOut]:
    """Newest first (docs/question-bank.md — newest first), ordered by
    `updated_at` so a conversation with a fresh turn bubbles back to the top
    rather than staying pinned at its creation time."""
    conversations = (
        (await session.execute(select(Conversation).order_by(Conversation.updated_at.desc())))
        .scalars()
        .all()
    )
    return [_to_conversation_out(conversation) for conversation in conversations]


@router.post("", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
async def create_conversation(session: AsyncSession = Depends(get_session)) -> ConversationOut:
    """Creates an empty conversation — no body needed. `title` starts blank
    and is filled in from the first user message by `POST .../messages`."""
    conversation = Conversation(title="")
    session.add(conversation)
    await session.commit()
    await session.refresh(conversation)
    return _to_conversation_out(conversation)


@router.get("/{conversation_id}", response_model=ConversationDetailOut)
async def get_conversation(
    conversation_id: int, session: AsyncSession = Depends(get_session)
) -> ConversationDetailOut:
    conversation = await _get_conversation_or_404(conversation_id, session)
    messages = (
        (
            await session.execute(
                select(ConversationMessage)
                .where(ConversationMessage.conversation_id == conversation_id)
                .order_by(ConversationMessage.id)
            )
        )
        .scalars()
        .all()
    )
    return ConversationDetailOut(
        **_to_conversation_out(conversation).model_dump(),
        messages=[_to_message_out(message) for message in messages],
    )


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: int, session: AsyncSession = Depends(get_session)
) -> None:
    """`conversation_messages.conversation_id` is `ON DELETE CASCADE`, so
    deleting the conversation row deletes every one of its messages in the
    same statement."""
    conversation = await _get_conversation_or_404(conversation_id, session)
    await session.delete(conversation)
    await session.commit()


@router.post(
    "/{conversation_id}/messages",
    response_model=PostMessageOut,
    status_code=status.HTTP_201_CREATED,
)
async def post_message(
    conversation_id: int,
    body: ConversationMessageIn,
    session: AsyncSession = Depends(get_session),
) -> PostMessageOut:
    """Stores the user's message, derives the conversation title from it if
    this is the first user message (docs/question-bank.md — 標題由第一則使
    用者訊息截斷產生), and enqueues exactly one `bank_agent_turn` job for
    this turn (docs/question-bank.md — 一個回合＝一個 job)."""
    conversation = await _get_conversation_or_404(conversation_id, session)
    settings = get_settings()

    is_first_user_message = (
        await session.execute(
            select(ConversationMessage.id).where(
                ConversationMessage.conversation_id == conversation_id,
                ConversationMessage.role == "user",
            )
        )
    ).first() is None

    message = ConversationMessage(
        conversation_id=conversation_id, role="user", content=body.content
    )
    session.add(message)

    if is_first_user_message:
        conversation.title = body.content[: settings.conversation_title_max_length]

    await session.commit()
    await session.refresh(message)

    job = Job(
        kind="bank_agent_turn",
        payload={
            "conversation_id": conversation_id,
            "message_id": message.id,
            "selected_question_ids": body.selected_question_ids,
        },
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)

    return PostMessageOut(job_id=job.id, message_id=message.id)
