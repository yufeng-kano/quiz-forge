"""OpenAI-compatible LLM client (docs/architecture.md — LLM 介接)."""

from backend.llm.client import LLMClient, LLMResponseError, VisionImage, get_llm_client

__all__ = ["LLMClient", "LLMResponseError", "VisionImage", "get_llm_client"]
