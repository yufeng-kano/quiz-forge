"""`GET /v1/usage` — aggregate LLM token totals grouped by model and by purpose.

Backs the future usage page (.rule 使用者體驗規則 — 累計用量必須可查看);
every value comes straight from `llm_usage`, written automatically by
`backend.llm.client.LLMClient` on every chat/embeddings call.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_session
from backend.models.llm_usage import LlmUsage
from backend.schemas.usage import ModelUsage, PurposeUsage, UsageOut, UsageTotals

router = APIRouter(prefix="/usage", tags=["usage"])


@router.get("", response_model=UsageOut)
async def get_usage(session: AsyncSession = Depends(get_session)) -> UsageOut:
    by_model_rows = (
        await session.execute(
            select(
                LlmUsage.model,
                func.coalesce(func.sum(LlmUsage.prompt_tokens), 0).label("prompt_tokens"),
                func.coalesce(func.sum(LlmUsage.completion_tokens), 0).label("completion_tokens"),
                func.count().label("call_count"),
            ).group_by(LlmUsage.model)
        )
    ).all()
    by_purpose_rows = (
        await session.execute(
            select(
                LlmUsage.purpose,
                func.coalesce(func.sum(LlmUsage.prompt_tokens), 0).label("prompt_tokens"),
                func.coalesce(func.sum(LlmUsage.completion_tokens), 0).label("completion_tokens"),
                func.count().label("call_count"),
            ).group_by(LlmUsage.purpose)
        )
    ).all()

    by_model = [
        ModelUsage(
            model=row.model,
            prompt_tokens=row.prompt_tokens,
            completion_tokens=row.completion_tokens,
            total_tokens=row.prompt_tokens + row.completion_tokens,
            call_count=row.call_count,
        )
        for row in by_model_rows
    ]
    by_purpose = [
        PurposeUsage(
            purpose=row.purpose,
            prompt_tokens=row.prompt_tokens,
            completion_tokens=row.completion_tokens,
            total_tokens=row.prompt_tokens + row.completion_tokens,
            call_count=row.call_count,
        )
        for row in by_purpose_rows
    ]
    total = UsageTotals(
        prompt_tokens=sum(m.prompt_tokens for m in by_model),
        completion_tokens=sum(m.completion_tokens for m in by_model),
        total_tokens=sum(m.total_tokens for m in by_model),
        call_count=sum(m.call_count for m in by_model),
    )
    return UsageOut(total=total, by_model=by_model, by_purpose=by_purpose)
