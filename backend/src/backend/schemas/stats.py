"""Response schema for `GET /v1/stats` — the Dashboard overview
(docs/decisions/2026-08-15-ux-overhaul-feature-expansion.md F5)."""

from pydantic import BaseModel


class StatsOut(BaseModel):
    documents_by_status: dict[str, int]
    questions_by_status: dict[str, int]
    chunk_count: int
    category_count: int
    failed_job_count: int
    llm_call_count: int
    llm_prompt_tokens: int
    llm_completion_tokens: int
