"""Live smoke test against the real LLM provider configured in the root `.env`.

NOT part of the default test run — real network call, real token spend.
Opt in explicitly:

    RUN_LIVE_LLM_TESTS=1 DATABASE_URL=<reachable-postgres> \\
        uv run --project backend pytest backend/tests/test_llm_live.py -v

Reads the API key from `Settings` only (never touched, printed, or logged
here); requests are kept minimal (one-line prompts, `max_tokens` capped) to
keep spend near-zero.
"""

import os

import pytest
from pydantic import BaseModel
from sqlalchemy import select

from backend.core.config import get_settings
from backend.db.session import AsyncSessionLocal
from backend.llm.client import LLMClient
from backend.models.llm_usage import LlmUsage

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_LLM_TESTS") != "1",
    reason="live LLM smoke test opts in with RUN_LIVE_LLM_TESTS=1 (spends real API credits)",
)


class OneWord(BaseModel):
    word: str


async def test_live_embeddings_call_records_real_usage() -> None:
    settings = get_settings()
    assert settings.llm_api_key, "root .env must provide a real LLM_API_KEY for this test"
    client = LLMClient(settings=settings, session_factory=AsyncSessionLocal)

    vectors = await client.embed(texts=["hi"], purpose="live_smoke_test_embed")

    assert len(vectors) == 1
    assert len(vectors[0]) > 0

    async with AsyncSessionLocal() as session:
        rows = (
            (
                await session.execute(
                    select(LlmUsage).where(LlmUsage.purpose == "live_smoke_test_embed")
                )
            )
            .scalars()
            .all()
        )
    assert len(rows) == 1
    assert rows[0].prompt_tokens > 0


async def test_live_chat_structured_call_records_real_usage() -> None:
    settings = get_settings()
    assert settings.llm_api_key, "root .env must provide a real LLM_API_KEY for this test"
    client = LLMClient(settings=settings, session_factory=AsyncSessionLocal)

    result = await client.chat(
        messages=[
            {"role": "user", "content": "Reply with the single English word 'hello'."},
        ],
        response_model=OneWord,
        purpose="live_smoke_test_chat",
        max_tokens=32,
    )

    assert isinstance(result, OneWord)
    assert result.word

    async with AsyncSessionLocal() as session:
        rows = (
            (
                await session.execute(
                    select(LlmUsage).where(LlmUsage.purpose == "live_smoke_test_chat")
                )
            )
            .scalars()
            .all()
        )
    assert len(rows) == 1
    assert rows[0].prompt_tokens > 0
