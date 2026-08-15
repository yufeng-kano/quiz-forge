"""`backend.ingestion.classification` — real-Postgres test.

Hierarchical category dedup (subject/topic) is exactly the kind of logic
.rule flags as needing a real test: getting this wrong means every chunk
classified into an existing subject/topic silently creates a duplicate
`categories` row instead of reusing it.

The `classify_chunk` prompt-content tests below are unit-level (mocked LLM
transport, no live call): they assert the *request body* the fake transport
received actually contains the seeded existing category names, so the "the
prompt must include existing subjects/topics" behaviour (docs/ingestion.md —
分類 prompt 必須帶入既有科目清單...避免同義科目碎裂) is exercised for real
rather than mocked away.
"""

import json
from collections.abc import Callable

import httpx2
import openai
from sqlalchemy import select

from backend.core.config import Settings
from backend.db.session import AsyncSessionLocal
from backend.ingestion.classification import (
    classify_chunk,
    get_or_create_category,
    load_existing_categories,
)
from backend.llm.client import LLMClient
from backend.models.category import Category


async def test_get_or_create_category_creates_once() -> None:
    async with AsyncSessionLocal() as session:
        category = await get_or_create_category(session, "生物", parent_id=None)
        assert category.id is not None
        assert category.name == "生物"
        assert category.parent_id is None


async def test_get_or_create_category_reuses_existing_row_for_same_name_and_parent() -> None:
    async with AsyncSessionLocal() as session:
        first = await get_or_create_category(session, "生物", parent_id=None)
        second = await get_or_create_category(session, "生物", parent_id=None)
        assert first.id == second.id


async def test_get_or_create_category_same_name_different_parent_are_distinct() -> None:
    async with AsyncSessionLocal() as session:
        subject_a = await get_or_create_category(session, "生物", parent_id=None)
        subject_b = await get_or_create_category(session, "地球科學", parent_id=None)

        topic_under_a = await get_or_create_category(session, "光合作用", parent_id=subject_a.id)
        topic_under_b = await get_or_create_category(session, "光合作用", parent_id=subject_b.id)

        assert topic_under_a.id != topic_under_b.id
        assert topic_under_a.parent_id == subject_a.id
        assert topic_under_b.parent_id == subject_b.id


async def test_get_or_create_category_builds_a_two_level_hierarchy() -> None:
    async with AsyncSessionLocal() as session:
        subject = await get_or_create_category(session, "生物", parent_id=None)
        topic = await get_or_create_category(session, "呼吸作用", parent_id=subject.id)

        rows = (
            (await session.execute(select(Category).where(Category.id == topic.id)))
            .scalars()
            .all()
        )
        assert len(rows) == 1
        assert rows[0].parent_id == subject.id


# ---------------------------------------------------------------------------
# classify_chunk — prompt must include existing categories (mocked transport)
# ---------------------------------------------------------------------------


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
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        },
    )


def _fake_llm_client(handler: Callable[[httpx2.Request], httpx2.Response]) -> LLMClient:
    settings = Settings(
        llm_base_url="https://llm.test/v1", llm_api_key="test-key-not-real", text_model="test-text"
    )
    fake_openai_client = openai.AsyncOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler)),
    )
    return LLMClient(
        settings=settings, session_factory=AsyncSessionLocal, openai_client=fake_openai_client
    )


def _canned_classification_handler(
    captured: list[httpx2.Request],
) -> Callable[[httpx2.Request], httpx2.Response]:
    def handler(request: httpx2.Request) -> httpx2.Response:
        captured.append(request)
        body = json.loads(request.content)
        return _chat_completion_response(
            model=body["model"],
            content={
                "subject": "資訊工程",
                "topic": "網路管理",
                "difficulty": "中等",
                "tags": ["TCP/IP"],
            },
        )

    return handler


async def test_classify_chunk_prompt_includes_existing_subject_and_topic_names() -> None:
    async with AsyncSessionLocal() as session:
        subject = await get_or_create_category(session, "資訊工程", parent_id=None)
        await get_or_create_category(session, "網路管理", parent_id=subject.id)
        await get_or_create_category(session, "資料庫", parent_id=subject.id)
        await get_or_create_category(session, "生物", parent_id=None)

    captured: list[httpx2.Request] = []
    fake_client = _fake_llm_client(_canned_classification_handler(captured))

    async with AsyncSessionLocal() as session:
        result = await classify_chunk(fake_client, session, "TCP/IP 協定簡介。", Settings())

    assert result.subject == "資訊工程"
    assert len(captured) == 1
    prompt_text = json.loads(captured[0].content)["messages"][0]["content"]
    assert "資訊工程" in prompt_text
    assert "網路管理" in prompt_text
    assert "資料庫" in prompt_text
    assert "生物" in prompt_text
    assert "重用" in prompt_text  # the reuse instruction itself is present


async def test_classify_chunk_prompt_notes_no_existing_categories_when_tree_is_empty() -> None:
    captured: list[httpx2.Request] = []
    fake_client = _fake_llm_client(_canned_classification_handler(captured))

    async with AsyncSessionLocal() as session:
        await classify_chunk(fake_client, session, "全新內容。", Settings())

    prompt_text = json.loads(captured[0].content)["messages"][0]["content"]
    assert "目前尚無既有分類" in prompt_text


async def test_load_existing_categories_caps_subjects_and_topics_per_subject() -> None:
    async with AsyncSessionLocal() as session:
        for subject_index in range(3):
            subject = await get_or_create_category(session, f"科目{subject_index}", parent_id=None)
            for topic_index in range(3):
                await get_or_create_category(
                    session, f"主題{subject_index}-{topic_index}", parent_id=subject.id
                )

        capped = await load_existing_categories(
            session, subjects_limit=2, topics_per_subject_limit=1
        )

    assert len(capped) == 2
    for _subject_name, topic_names in capped:
        assert len(topic_names) == 1
