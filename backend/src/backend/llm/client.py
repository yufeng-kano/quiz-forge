"""OpenAI-compatible LLM client (docs/architecture.md — 一律 OpenAI-compatible，
預設 OpenRouter；.rule 開發規則 — 不做 Anthropic message format).

Every chat/embeddings call goes through `LLMClient` so that, uniformly:

- concurrency is capped by one `asyncio.Semaphore` sized from `LLM_CONCURRENCY`;
- structured output always uses `response_format: json_schema` in strict
  mode and returns a validated Pydantic instance — callers never parse free
  text themselves;
- every call automatically records a `llm_usage` row (model/purpose/tokens),
  so callers (job handlers) never have to remember to log usage themselves.
"""

import asyncio
import base64
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import TypeVar

import openai
from openai import AsyncOpenAI
from openai.types.chat import (
    ChatCompletionContentPartImageParam,
    ChatCompletionContentPartParam,
    ChatCompletionContentPartTextParam,
    ChatCompletionMessageParam,
    ChatCompletionUserMessageParam,
)
from openai.types.shared_params import ResponseFormatJSONSchema
from openai.types.shared_params.response_format_json_schema import JSONSchema
from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.core.config import Settings, get_settings
from backend.db.session import AsyncSessionLocal
from backend.llm.schema import build_strict_json_schema
from backend.llm.usage import record_usage

logger = logging.getLogger(__name__)

ModelT = TypeVar("ModelT", bound=BaseModel)


class LLMResponseError(RuntimeError):
    """Raised when a structured-output response was empty or failed schema validation."""


@dataclass(frozen=True)
class VisionImage:
    """One image to attach to a vision chat call."""

    data: bytes
    mime_type: str = "image/png"

    def to_data_uri(self) -> str:
        encoded = base64.b64encode(self.data).decode("ascii")
        return f"data:{self.mime_type};base64,{encoded}"


def _response_format_for(response_model: type[BaseModel]) -> ResponseFormatJSONSchema:
    schema: JSONSchema = {
        "name": response_model.__name__,
        "schema": build_strict_json_schema(response_model),
        "strict": True,
    }
    return {"type": "json_schema", "json_schema": schema}


class LLMClient:
    """Thin async wrapper around `openai.AsyncOpenAI` for OpenAI-compatible providers."""

    def __init__(
        self,
        settings: Settings,
        session_factory: async_sessionmaker[AsyncSession] = AsyncSessionLocal,
        openai_client: AsyncOpenAI | None = None,
    ) -> None:
        self._settings = settings
        self._session_factory = session_factory
        self._client = openai_client or AsyncOpenAI(
            base_url=settings.llm_base_url, api_key=settings.llm_api_key
        )
        self._semaphore = asyncio.Semaphore(settings.llm_concurrency)

    async def _record(
        self, model: str, purpose: str, prompt_tokens: int, completion_tokens: int
    ) -> None:
        await record_usage(
            self._session_factory,
            model=model,
            purpose=purpose,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

    async def _structured_completion(
        self,
        *,
        messages: list[ChatCompletionMessageParam],
        response_model: type[ModelT],
        purpose: str,
        model: str,
        max_tokens: int | None,
        temperature: float | None,
    ) -> ModelT:
        async with self._semaphore:
            completion = await self._client.chat.completions.create(
                model=model,
                messages=messages,
                response_format=_response_format_for(response_model),
                max_tokens=max_tokens if max_tokens is not None else openai.omit,
                temperature=temperature if temperature is not None else openai.omit,
            )

        usage = completion.usage
        prompt_tokens = usage.prompt_tokens if usage is not None else 0
        completion_tokens = usage.completion_tokens if usage is not None else 0
        await self._record(model, purpose, prompt_tokens, completion_tokens)

        content = completion.choices[0].message.content
        if content is None:
            raise LLMResponseError(f"empty structured-output response for purpose {purpose!r}")
        try:
            return response_model.model_validate_json(content)
        except ValidationError as exc:
            raise LLMResponseError(
                f"response failed schema validation for purpose {purpose!r}: {exc}"
            ) from exc

    async def chat(
        self,
        *,
        messages: list[ChatCompletionMessageParam],
        response_model: type[ModelT],
        purpose: str,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> ModelT:
        """Text chat completion constrained to `response_model` (default `TEXT_MODEL`)."""
        return await self._structured_completion(
            messages=messages,
            response_model=response_model,
            purpose=purpose,
            model=model or self._settings.text_model,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    async def vision(
        self,
        *,
        prompt: str,
        images: Sequence[VisionImage],
        response_model: type[ModelT],
        purpose: str,
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> ModelT:
        """Vision chat completion (image + text prompt) constrained to `response_model`
        (default `VISION_MODEL`)."""
        if not images:
            raise ValueError("vision() requires at least one image")

        text_part: ChatCompletionContentPartTextParam = {"type": "text", "text": prompt}
        content: list[ChatCompletionContentPartParam] = [text_part]
        for image in images:
            image_part: ChatCompletionContentPartImageParam = {
                "type": "image_url",
                "image_url": {"url": image.to_data_uri()},
            }
            content.append(image_part)

        message: ChatCompletionUserMessageParam = {"role": "user", "content": content}
        return await self._structured_completion(
            messages=[message],
            response_model=response_model,
            purpose=purpose,
            model=model or self._settings.vision_model,
            max_tokens=max_tokens,
            temperature=None,
        )

    async def embed(
        self,
        *,
        texts: list[str],
        purpose: str,
        model: str | None = None,
    ) -> list[list[float]]:
        """Embed `texts` (default `EMBEDDING_MODEL`), preserving input order."""
        if not texts:
            raise ValueError("embed() requires at least one input text")
        target_model = model or self._settings.embedding_model

        async with self._semaphore:
            response = await self._client.embeddings.create(model=target_model, input=texts)

        await self._record(target_model, purpose, response.usage.prompt_tokens, 0)

        ordered = sorted(response.data, key=lambda item: item.index)
        return [list(item.embedding) for item in ordered]


@lru_cache
def get_llm_client() -> LLMClient:
    """Process-wide `LLMClient` singleton, built from settings."""
    return LLMClient(settings=get_settings())
