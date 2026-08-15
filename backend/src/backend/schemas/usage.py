"""Response schema for `GET /v1/usage` — aggregate LLM token accounting."""

from pydantic import BaseModel


class ModelUsage(BaseModel):
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    call_count: int


class PurposeUsage(BaseModel):
    purpose: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    call_count: int


class UsageTotals(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    call_count: int


class UsageOut(BaseModel):
    total: UsageTotals
    by_model: list[ModelUsage]
    by_purpose: list[PurposeUsage]
