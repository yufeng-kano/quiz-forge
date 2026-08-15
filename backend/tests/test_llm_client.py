"""`backend.llm.client.LLMClient` tests.

The OpenAI transport is faked at the HTTP layer with `httpx2.MockTransport`
(the `openai` SDK in this project talks over the `httpx2` package, not
`httpx` — see `AsyncOpenAI.__init__`'s `http_client` param). Every request
that reaches the fake transport is captured so we can assert on the actual
`response_format` / `messages` / embeddings request bodies the client sent,
and every test checks the real `llm_usage` row written by the client — the
logic under test (schema strictening, message building, usage bookkeeping)
is never mocked away, only the network call is.
"""

import json
from collections.abc import Callable

import httpx2
import openai
import pytest
from pydantic import BaseModel
from sqlalchemy import select

from backend.core.config import Settings
from backend.db.session import AsyncSessionLocal
from backend.llm.client import LLMClient, LLMResponseError, VisionImage
from backend.models.llm_usage import LlmUsage


class Animal(BaseModel):
    name: str
    legs: int


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    """A fully-isolated `Settings` instance — never reads the real root `.env`."""
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    return Settings(
        llm_base_url="https://llm.test/v1",
        llm_api_key="test-key-not-real",
        text_model="test-text-model",
        vision_model="test-vision-model",
        embedding_model="test-embed-model",
        llm_concurrency=2,
    )


def _make_client(
    settings: Settings, handler: Callable[[httpx2.Request], httpx2.Response]
) -> LLMClient:
    fake_openai_client = openai.AsyncOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler)),
    )
    return LLMClient(
        settings=settings, session_factory=AsyncSessionLocal, openai_client=fake_openai_client
    )


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
            "usage": {"prompt_tokens": 12, "completion_tokens": 7, "total_tokens": 19},
        },
    )


def _embeddings_response(*, model: str, vectors: list[list[float]]) -> httpx2.Response:
    return httpx2.Response(
        200,
        json={
            "object": "list",
            "model": model,
            "data": [
                {"object": "embedding", "index": i, "embedding": vec}
                for i, vec in enumerate(vectors)
            ],
            "usage": {"prompt_tokens": 5, "total_tokens": 5},
        },
    )


async def _usage_rows_for(purpose: str) -> list[LlmUsage]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(LlmUsage).where(LlmUsage.purpose == purpose))
        return list(result.scalars().all())


async def test_chat_returns_validated_model_and_sends_strict_json_schema(
    settings: Settings,
) -> None:
    captured: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured.append(request)
        return _chat_completion_response(
            model=settings.text_model, content={"name": "Cat", "legs": 4}
        )

    client = _make_client(settings, handler)

    result = await client.chat(
        messages=[{"role": "user", "content": "name an animal"}],
        response_model=Animal,
        purpose="test_purpose_chat",
    )

    assert result == Animal(name="Cat", legs=4)

    assert len(captured) == 1
    request = captured[0]
    assert request.url.path == "/v1/chat/completions"
    body = json.loads(request.content)
    assert body["model"] == "test-text-model"
    assert body["response_format"]["type"] == "json_schema"
    json_schema = body["response_format"]["json_schema"]
    assert json_schema["strict"] is True
    assert json_schema["name"] == "Animal"
    schema = json_schema["schema"]
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {"name", "legs"}

    rows = await _usage_rows_for("test_purpose_chat")
    assert len(rows) == 1
    assert rows[0].model == "test-text-model"
    assert rows[0].prompt_tokens == 12
    assert rows[0].completion_tokens == 7


async def test_chat_raises_on_schema_validation_failure(settings: Settings) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return _chat_completion_response(model=settings.text_model, content={"name": "Cat"})

    client = _make_client(settings, handler)

    with pytest.raises(LLMResponseError):
        await client.chat(
            messages=[{"role": "user", "content": "name an animal"}],
            response_model=Animal,
            purpose="test_purpose_invalid",
        )

    # the request still consumed real tokens even though validation failed
    # afterward — usage must still be recorded.
    rows = await _usage_rows_for("test_purpose_invalid")
    assert len(rows) == 1


async def test_vision_sends_image_data_uri_and_uses_vision_model(settings: Settings) -> None:
    captured: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured.append(request)
        return _chat_completion_response(
            model=settings.vision_model, content={"name": "Dog", "legs": 4}
        )

    client = _make_client(settings, handler)

    image = VisionImage(data=b"\x89PNG-fake-bytes", mime_type="image/png")
    result = await client.vision(
        prompt="what animal is this?",
        images=[image],
        response_model=Animal,
        purpose="test_purpose_vision",
    )

    assert result == Animal(name="Dog", legs=4)
    body = json.loads(captured[0].content)
    assert body["model"] == "test-vision-model"
    content_parts = body["messages"][0]["content"]
    assert content_parts[0] == {"type": "text", "text": "what animal is this?"}
    image_part = content_parts[1]
    assert image_part["type"] == "image_url"
    assert image_part["image_url"]["url"] == image.to_data_uri()
    assert image_part["image_url"]["url"].startswith("data:image/png;base64,")

    rows = await _usage_rows_for("test_purpose_vision")
    assert len(rows) == 1
    assert rows[0].model == "test-vision-model"


async def test_embed_sends_input_texts_and_returns_ordered_vectors(settings: Settings) -> None:
    captured: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured.append(request)
        # deliberately return out of order to prove the client re-sorts by index
        return _embeddings_response(
            model=settings.embedding_model,
            vectors=[[9.0, 9.0], [1.0, 1.0]],
        )

    client = _make_client(settings, handler)

    vectors = await client.embed(texts=["first", "second"], purpose="test_purpose_embed")

    assert vectors == [[9.0, 9.0], [1.0, 1.0]]

    body = json.loads(captured[0].content)
    assert body["model"] == "test-embed-model"
    assert body["input"] == ["first", "second"]

    rows = await _usage_rows_for("test_purpose_embed")
    assert len(rows) == 1
    assert rows[0].model == "test-embed-model"
    assert rows[0].prompt_tokens == 5
    assert rows[0].completion_tokens == 0
