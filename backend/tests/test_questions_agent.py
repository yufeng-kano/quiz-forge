"""`bank_agent_turn` job handler tests (.rule 反偷懶規則 — job queue 屬高風險
邏輯，須有測試; docs/question-bank.md 題庫選題助手（對話 agent）; docs/decisions/
2026-08-17-bank-agent-semantic-selection.md D4/D5/D6).

The LLM transport is faked exactly like `test_questions_generation.py`
(`httpx2.MockTransport`) so the actual bounded-loop logic under test — step
dispatch, the shared `search_questions` query path, proposed-id validation,
the `steps` jsonb log, and step-cap termination — is never mocked away, only
the network call is. Real Postgres throughout (no DB mocking).
"""

import json
from collections.abc import Callable

import httpx2
import openai
import pytest
from factories import create_job
from pydantic import ValidationError
from sqlalchemy import select

import backend.questions.agent as agent_module
from backend.core.config import Settings, get_settings
from backend.db.session import AsyncSessionLocal
from backend.jobs.worker import claim_job, run_claimed_job
from backend.llm.client import LLMClient
from backend.llm.schema import build_strict_json_schema
from backend.models.category import Category
from backend.models.chunk import Chunk
from backend.models.conversation import Conversation, ConversationMessage
from backend.models.document import Document
from backend.models.job import Job
from backend.models.question import Question
from backend.questions.agent import BankAgentStep

SINGLE_CHOICE_PAYLOAD: dict[str, object] = {
    "stem": "光合作用發生在細胞的哪個構造？",
    "options": ["粒線體", "葉綠體", "細胞核", "核糖體"],
    "answer_index": 1,
    "explanation": None,
}


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


async def _make_document() -> int:
    async with AsyncSessionLocal() as session:
        document = Document(source_type="upload", title="doc", status="ready")
        session.add(document)
        await session.commit()
        await session.refresh(document)
        return document.id


async def _make_category(name: str = "分類") -> int:
    async with AsyncSessionLocal() as session:
        category = Category(name=name, parent_id=None)
        session.add(category)
        await session.commit()
        await session.refresh(category)
        return category.id


async def _make_chunk(document_id: int, category_id: int | None) -> int:
    async with AsyncSessionLocal() as session:
        chunk = Chunk(document_id=document_id, content="內容", category_id=category_id)
        session.add(chunk)
        await session.commit()
        await session.refresh(chunk)
        return chunk.id


async def _make_question(
    *,
    question_type: str = "single_choice",
    difficulty: str | None = None,
    status: str = "approved",
    source_chunk_ids: list[int] | None = None,
    payload: dict[str, object] | None = None,
) -> int:
    async with AsyncSessionLocal() as session:
        question = Question(
            type=question_type,
            difficulty=difficulty,
            status=status,
            payload=payload or SINGLE_CHOICE_PAYLOAD,
            source_chunk_ids=source_chunk_ids or [],
        )
        session.add(question)
        await session.commit()
        await session.refresh(question)
        return question.id


async def _make_conversation(title: str = "") -> int:
    async with AsyncSessionLocal() as session:
        conversation = Conversation(title=title)
        session.add(conversation)
        await session.commit()
        await session.refresh(conversation)
        return conversation.id


async def _make_user_message(conversation_id: int, content: str) -> int:
    async with AsyncSessionLocal() as session:
        message = ConversationMessage(conversation_id=conversation_id, role="user", content=content)
        session.add(message)
        await session.commit()
        await session.refresh(message)
        return message.id


async def _turn_payload(
    content: str = "幫我找一題單選題", selected_question_ids: list[int] | None = None
) -> tuple[int, dict[str, object]]:
    conversation_id = await _make_conversation()
    message_id = await _make_user_message(conversation_id, content)
    return conversation_id, {
        "conversation_id": conversation_id,
        "message_id": message_id,
        "selected_question_ids": selected_question_ids or [],
    }


async def _run_job(payload: dict[str, object]) -> int:
    job_id = await create_job("bank_agent_turn", payload=payload)
    async with AsyncSessionLocal() as session:
        claimed = await claim_job(session)
        assert claimed is not None
        assert claimed.id == job_id
    await run_claimed_job(AsyncSessionLocal, job_id)
    return job_id


async def _get_job(job_id: int) -> Job:
    async with AsyncSessionLocal() as session:
        job = await session.get(Job, job_id)
        assert job is not None
        return job


async def _assistant_messages(conversation_id: int) -> list[ConversationMessage]:
    async with AsyncSessionLocal() as session:
        rows = (
            (
                await session.execute(
                    select(ConversationMessage)
                    .where(
                        ConversationMessage.conversation_id == conversation_id,
                        ConversationMessage.role == "assistant",
                    )
                    .order_by(ConversationMessage.id)
                )
            )
            .scalars()
            .all()
        )
        return list(rows)


def _step_dict(entry: object) -> dict[str, object]:
    """Narrows one `steps` jsonb entry (typed `list[object]` on the ORM
    model, since jsonb is opaque at the type level) to a plain dict so tests
    can index into it -- a real runtime check, not a suppression."""
    assert isinstance(entry, dict)
    return entry


def _search_step(**search_overrides: object) -> dict[str, object]:
    search: dict[str, object] = {
        "similar_to": None,
        "q": None,
        "type": None,
        "difficulty": None,
        "category_id": None,
        "limit": None,
    }
    search.update(search_overrides)
    return {"action": "search", "search": search, "question_ids": None, "reply": None}


def _propose_step(question_ids: list[int], reply: str) -> dict[str, object]:
    return {"action": "propose", "search": None, "question_ids": question_ids, "reply": reply}


def _reply_step(reply: str) -> dict[str, object]:
    return {"action": "reply", "search": None, "question_ids": None, "reply": reply}


def _chat_completion_response(*, model: str, content: dict[str, object]) -> httpx2.Response:
    return httpx2.Response(
        200,
        json={
            "id": "chatcmpl-test",
            "object": "chat.completion",
            "created": 0,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": json.dumps(content)},
                }
            ],
            "usage": {"prompt_tokens": 5, "completion_tokens": 5, "total_tokens": 10},
        },
    )


def _scripted_handler(
    steps: list[dict[str, object]],
) -> Callable[[httpx2.Request], httpx2.Response]:
    """Replies with `steps[call_count]` on each successive chat call; used
    for tests where the exact call count is bounded/known."""
    call_count = 0

    def handler(request: httpx2.Request) -> httpx2.Response:
        nonlocal call_count
        body = json.loads(request.content)
        content = steps[call_count]
        call_count += 1
        return _chat_completion_response(model=body["model"], content=content)

    return handler


def _repeating_handler(step: dict[str, object]) -> Callable[[httpx2.Request], httpx2.Response]:
    """Always replies with the same step — used to force the step cap."""

    def handler(request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content)
        return _chat_completion_response(model=body["model"], content=step)

    return handler


def _fake_llm_client(handler: Callable[[httpx2.Request], httpx2.Response]) -> LLMClient:
    settings = Settings(
        llm_base_url="https://llm.test/v1",
        llm_api_key="test-key-not-real",
        text_model="test-text-model",
    )
    fake_openai_client = openai.AsyncOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler)),
    )
    return LLMClient(
        settings=settings, session_factory=AsyncSessionLocal, openai_client=fake_openai_client
    )


# ---------------------------------------------------------------------------
# BankAgentStep schema (D4 — response_format: json_schema, never free text)
# ---------------------------------------------------------------------------


def test_bank_agent_step_rejects_unknown_action() -> None:
    with pytest.raises(ValidationError):
        BankAgentStep.model_validate(
            {"action": "delete", "search": None, "question_ids": None, "reply": None}
        )


def test_bank_agent_step_accepts_every_documented_action() -> None:
    for action in ("search", "propose", "reply"):
        step = BankAgentStep.model_validate(
            {"action": action, "search": None, "question_ids": None, "reply": None}
        )
        assert step.action == action


def test_bank_agent_step_strict_json_schema_makes_every_field_required_but_nullable() -> None:
    """`response_format: json_schema` strict mode (backend.llm.schema) needs
    every key in `required` even though `search`/`question_ids`/`reply` are
    only meaningful for some actions -- they're nullable types instead."""
    schema = build_strict_json_schema(BankAgentStep)
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {"action", "search", "question_ids", "reply"}


# ---------------------------------------------------------------------------
# Bounded loop: search -> propose terminates, steps log contents
# ---------------------------------------------------------------------------


async def test_search_then_propose_terminates_and_logs_both_steps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document_id = await _make_document()
    category_id = await _make_category()
    chunk_id = await _make_chunk(document_id, category_id)
    approved_id = await _make_question(source_chunk_ids=[chunk_id])

    conversation_id, payload = await _turn_payload("找一題單選題")

    handler = _scripted_handler(
        [
            _search_step(type="single_choice"),
            _propose_step([approved_id], "推薦這一題單選題。"),
        ]
    )
    fake_client = _fake_llm_client(handler)
    monkeypatch.setattr(agent_module, "get_llm_client", lambda: fake_client)

    job_id = await _run_job(payload)
    job = await _get_job(job_id)

    assert job.status == "done"
    assert job.error is None
    assert job.progress == f"2/{get_settings().bank_agent_max_steps}"

    messages = await _assistant_messages(conversation_id)
    assert len(messages) == 1
    assistant_message = messages[0]
    assert assistant_message.content == "推薦這一題單選題。"
    assert assistant_message.proposed_question_ids == [approved_id]

    assert assistant_message.steps is not None
    assert len(assistant_message.steps) == 2
    search_entry = _step_dict(assistant_message.steps[0])
    propose_entry = _step_dict(assistant_message.steps[1])
    assert search_entry["step"] == 1
    assert search_entry["action"] == "search"
    assert search_entry["hit_count"] == 1
    search_filters = _step_dict(search_entry["filters"])
    assert search_filters["type"] == "single_choice"
    assert search_filters["limit"] == get_settings().bank_agent_search_limit
    assert propose_entry == {"step": 2, "action": "propose", "question_ids": [approved_id]}

    # `conversations.updated_at` is explicitly touched by the handler so
    # "newest first" listing reflects turn activity, not just creation time.
    async with AsyncSessionLocal() as session:
        conversation = await session.get(Conversation, conversation_id)
        assert conversation is not None
        assert conversation.updated_at >= conversation.created_at


async def test_reply_action_terminates_without_any_proposal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversation_id, payload = await _turn_payload("題庫裡有什麼？")

    handler = _scripted_handler([_reply_step("可以先告訴我你想考哪個科目嗎？")])
    fake_client = _fake_llm_client(handler)
    monkeypatch.setattr(agent_module, "get_llm_client", lambda: fake_client)

    job_id = await _run_job(payload)
    job = await _get_job(job_id)
    assert job.status == "done"

    messages = await _assistant_messages(conversation_id)
    assert len(messages) == 1
    assert messages[0].content == "可以先告訴我你想考哪個科目嗎？"
    assert messages[0].proposed_question_ids == []
    assert messages[0].steps == [{"step": 1, "action": "reply"}]


# ---------------------------------------------------------------------------
# Step cap forces termination with an explanatory reply (never silent)
# ---------------------------------------------------------------------------


async def test_step_cap_forces_termination_with_explanatory_reply(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BANK_AGENT_MAX_STEPS", "2")
    get_settings.cache_clear()
    try:
        conversation_id, payload = await _turn_payload("一直找一直找")

        # The model only ever proposes "search" -- it never reaches
        # propose/reply on its own, forcing the step cap.
        handler = _repeating_handler(_search_step())
        fake_client = _fake_llm_client(handler)
        monkeypatch.setattr(agent_module, "get_llm_client", lambda: fake_client)

        job_id = await _run_job(payload)
        job = await _get_job(job_id)

        # Capped, not an error -- .rule 禁止吞例外, but hitting the step cap
        # isn't an exception, it's a defined, explained ending.
        assert job.status == "done"
        assert job.progress == "2/2"

        messages = await _assistant_messages(conversation_id)
        assert len(messages) == 1
        assistant_message = messages[0]
        assert assistant_message.proposed_question_ids == []
        # Must explain the cap, not silently truncate.
        assert "2 步" in assistant_message.content
        assert assistant_message.steps is not None
        assert len(assistant_message.steps) == 2
        assert all(
            _step_dict(entry)["action"] == "search" for entry in assistant_message.steps
        )
    finally:
        get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Proposed-id validation: unknown / non-approved ids are dropped, not stored
# ---------------------------------------------------------------------------


async def test_propose_drops_unknown_and_non_approved_ids_but_logs_the_raw_proposal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    approved_id = await _make_question(status="approved")
    draft_id = await _make_question(status="draft")
    rejected_id = await _make_question(status="rejected")
    missing_id = draft_id + rejected_id + approved_id + 10_000  # guaranteed not to exist

    conversation_id, payload = await _turn_payload("推薦幾題")

    proposed = [approved_id, draft_id, rejected_id, missing_id]
    handler = _scripted_handler([_propose_step(proposed, "這是我的推薦。")])
    fake_client = _fake_llm_client(handler)
    monkeypatch.setattr(agent_module, "get_llm_client", lambda: fake_client)

    job_id = await _run_job(payload)
    job = await _get_job(job_id)
    assert job.status == "done"

    messages = await _assistant_messages(conversation_id)
    assert len(messages) == 1
    assistant_message = messages[0]
    # Only the approved id survives -- draft/rejected/unknown ids are dropped
    # rather than stored as a proposal the frontend can't act on.
    assert assistant_message.proposed_question_ids == [approved_id]
    # The steps log still records exactly what the model asked for, for the
    # 「查詢過程」audit trail, even though some of it was invalid.
    assert assistant_message.steps == [
        {"step": 1, "action": "propose", "question_ids": proposed}
    ]


async def test_propose_with_no_valid_ids_yields_empty_proposal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversation_id, payload = await _turn_payload("推薦一題")

    handler = _scripted_handler([_propose_step([999_999], "找不到合適的題目。")])
    fake_client = _fake_llm_client(handler)
    monkeypatch.setattr(agent_module, "get_llm_client", lambda: fake_client)

    job_id = await _run_job(payload)
    job = await _get_job(job_id)
    assert job.status == "done"

    messages = await _assistant_messages(conversation_id)
    assert messages[0].proposed_question_ids == []


# ---------------------------------------------------------------------------
# search reuses the shared search_questions path (D3) and only ever sees
# status=approved questions, never draft/rejected ones.
# ---------------------------------------------------------------------------


async def test_search_step_only_ever_finds_approved_questions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    approved_id = await _make_question(status="approved")
    await _make_question(status="draft")
    await _make_question(status="rejected")

    conversation_id, payload = await _turn_payload("找題目")

    handler = _scripted_handler(
        [_search_step(), _propose_step([approved_id], "只有這一題可以推薦。")]
    )
    fake_client = _fake_llm_client(handler)
    monkeypatch.setattr(agent_module, "get_llm_client", lambda: fake_client)

    job_id = await _run_job(payload)
    job = await _get_job(job_id)
    assert job.status == "done"

    messages = await _assistant_messages(conversation_id)
    assert messages[0].steps is not None
    search_entry = _step_dict(messages[0].steps[0])
    assert search_entry["hit_count"] == 1  # not 3 -- draft/rejected never counted


async def test_search_limit_is_capped_at_bank_agent_search_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BANK_AGENT_SEARCH_LIMIT", "5")
    get_settings.cache_clear()
    try:
        conversation_id, payload = await _turn_payload("找題目")
        # The model asks for far more than the configured cap.
        handler = _scripted_handler(
            [_search_step(limit=999), _reply_step("查完了。")]
        )
        fake_client = _fake_llm_client(handler)
        monkeypatch.setattr(agent_module, "get_llm_client", lambda: fake_client)

        job_id = await _run_job(payload)
        job = await _get_job(job_id)
        assert job.status == "done"

        messages = await _assistant_messages(conversation_id)
        assert messages[0].steps is not None
        search_entry = _step_dict(messages[0].steps[0])
        assert _step_dict(search_entry["filters"])["limit"] == 5
    finally:
        get_settings.cache_clear()
