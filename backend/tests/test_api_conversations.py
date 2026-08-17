"""`/v1/conversations` through the real HTTP app (docs/question-bank.md 題庫
選題助手（對話 agent）相關 API; docs/decisions/2026-08-17-bank-agent-semantic-
selection.md D6).

The `client` fixture disables the job worker pool (see `conftest.py`), so
`POST .../messages` here only exercises message/title/job-row creation —
the `bank_agent_turn` handler itself (the bounded loop, structured output,
proposed-id validation) is covered end-to-end against a mocked LLM transport
in `test_questions_agent.py`.
"""

from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.core.config import get_settings
from backend.db.session import AsyncSessionLocal
from backend.models.conversation import Conversation, ConversationMessage
from backend.models.job import Job


async def _make_conversation(title: str = "") -> int:
    async with AsyncSessionLocal() as session:
        conversation = Conversation(title=title)
        session.add(conversation)
        await session.commit()
        await session.refresh(conversation)
        return conversation.id


async def _make_message(
    conversation_id: int, *, role: str = "user", content: str = "訊息"
) -> int:
    async with AsyncSessionLocal() as session:
        message = ConversationMessage(conversation_id=conversation_id, role=role, content=content)
        session.add(message)
        await session.commit()
        await session.refresh(message)
        return message.id


# ---------------------------------------------------------------------------
# POST /v1/conversations -- create
# ---------------------------------------------------------------------------


def test_create_conversation_starts_with_blank_title(client: TestClient) -> None:
    response = client.post("/v1/conversations")
    assert response.status_code == 201
    body = response.json()
    assert body["title"] == ""
    assert isinstance(body["id"], int)


# ---------------------------------------------------------------------------
# GET /v1/conversations -- list, newest first
# ---------------------------------------------------------------------------


def test_list_conversations_empty_when_none_exist(client: TestClient) -> None:
    response = client.get("/v1/conversations")
    assert response.status_code == 200
    assert response.json() == []


async def test_list_conversations_orders_newest_first_by_activity(client: TestClient) -> None:
    older_id = await _make_conversation("較早的對話")
    newer_id = await _make_conversation("較新的對話")

    response = client.get("/v1/conversations")
    assert response.status_code == 200
    ids = [row["id"] for row in response.json()]
    assert ids.index(newer_id) < ids.index(older_id)


# ---------------------------------------------------------------------------
# GET /v1/conversations/{id} -- detail incl. messages
# ---------------------------------------------------------------------------


def test_get_conversation_404_when_missing(client: TestClient) -> None:
    response = client.get("/v1/conversations/999999")
    assert response.status_code == 404


async def test_get_conversation_includes_messages_oldest_first(client: TestClient) -> None:
    conversation_id = await _make_conversation("對話")
    first_id = await _make_message(conversation_id, role="user", content="第一句")
    second_id = await _make_message(conversation_id, role="assistant", content="第二句")

    response = client.get(f"/v1/conversations/{conversation_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == conversation_id
    message_ids = [message["id"] for message in body["messages"]]
    assert message_ids == [first_id, second_id]
    assert body["messages"][1]["role"] == "assistant"


# ---------------------------------------------------------------------------
# DELETE /v1/conversations/{id} -- cascades to messages
# ---------------------------------------------------------------------------


async def test_delete_conversation_cascades_to_messages(client: TestClient) -> None:
    conversation_id = await _make_conversation("對話")
    await _make_message(conversation_id)

    response = client.delete(f"/v1/conversations/{conversation_id}")
    assert response.status_code == 204

    async with AsyncSessionLocal() as session:
        remaining = (
            (
                await session.execute(
                    select(ConversationMessage).where(
                        ConversationMessage.conversation_id == conversation_id
                    )
                )
            )
            .scalars()
            .all()
        )
    assert remaining == []
    assert client.get(f"/v1/conversations/{conversation_id}").status_code == 404


def test_delete_conversation_404_when_missing(client: TestClient) -> None:
    response = client.delete("/v1/conversations/999999")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# POST /v1/conversations/{id}/messages
# ---------------------------------------------------------------------------


def test_post_message_404_when_conversation_missing(client: TestClient) -> None:
    response = client.post(
        "/v1/conversations/999999/messages", json={"content": "找題目", "selected_question_ids": []}
    )
    assert response.status_code == 404


async def test_post_first_message_sets_title_and_enqueues_job(client: TestClient) -> None:
    conversation_id = await _make_conversation()

    response = client.post(
        f"/v1/conversations/{conversation_id}/messages",
        json={"content": "幫我找幾題三角函數的單選題", "selected_question_ids": [1, 2]},
    )
    assert response.status_code == 201
    body = response.json()
    assert isinstance(body["job_id"], int)
    assert isinstance(body["message_id"], int)

    async with AsyncSessionLocal() as session:
        conversation = await session.get(Conversation, conversation_id)
        assert conversation is not None
        assert conversation.title == "幫我找幾題三角函數的單選題"

        message = await session.get(ConversationMessage, body["message_id"])
        assert message is not None
        assert message.role == "user"
        assert message.content == "幫我找幾題三角函數的單選題"

        job = await session.get(Job, body["job_id"])
        assert job is not None
        assert job.kind == "bank_agent_turn"
        assert job.payload == {
            "conversation_id": conversation_id,
            "message_id": message.id,
            "selected_question_ids": [1, 2],
        }


async def test_post_message_title_truncated_to_setting(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setenv("CONVERSATION_TITLE_MAX_LENGTH", "5")
    get_settings.cache_clear()
    try:
        conversation_id = await _make_conversation()
        response = client.post(
            f"/v1/conversations/{conversation_id}/messages",
            json={"content": "一二三四五六七八九十", "selected_question_ids": []},
        )
        assert response.status_code == 201

        async with AsyncSessionLocal() as session:
            conversation = await session.get(Conversation, conversation_id)
            assert conversation is not None
            assert conversation.title == "一二三四五"
    finally:
        get_settings.cache_clear()


async def test_post_second_message_does_not_overwrite_the_title(client: TestClient) -> None:
    conversation_id = await _make_conversation()
    client.post(
        f"/v1/conversations/{conversation_id}/messages",
        json={"content": "第一句話", "selected_question_ids": []},
    )
    client.post(
        f"/v1/conversations/{conversation_id}/messages",
        json={"content": "第二句話，不該變成標題", "selected_question_ids": []},
    )

    async with AsyncSessionLocal() as session:
        conversation = await session.get(Conversation, conversation_id)
        assert conversation is not None
        assert conversation.title == "第一句話"

        user_messages = (
            (
                await session.execute(
                    select(ConversationMessage).where(
                        ConversationMessage.conversation_id == conversation_id,
                        ConversationMessage.role == "user",
                    )
                )
            )
            .scalars()
            .all()
        )
    assert len(user_messages) == 2


async def test_post_message_rejects_blank_content(client: TestClient) -> None:
    conversation_id = await _make_conversation()
    response = client.post(
        f"/v1/conversations/{conversation_id}/messages",
        json={"content": "", "selected_question_ids": []},
    )
    assert response.status_code == 422


async def test_post_message_defaults_selected_question_ids_to_empty(client: TestClient) -> None:
    conversation_id = await _make_conversation()
    response = client.post(
        f"/v1/conversations/{conversation_id}/messages", json={"content": "找題目"}
    )
    assert response.status_code == 201
    body = response.json()

    async with AsyncSessionLocal() as session:
        job = await session.get(Job, body["job_id"])
        assert job is not None
        assert job.payload["selected_question_ids"] == []
