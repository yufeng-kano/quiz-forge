"""`GET /v1/stats` — Dashboard overview (docs/decisions/2026-08-15-ux-
overhaul-feature-expansion.md F5): documents/questions by status, chunk and
category counts, failed-job count, cumulative LLM token/call usage.

A fixed, small set of aggregate queries (one `GROUP BY` per status
breakdown, one `COUNT`/`SUM` each for the rest) — never a per-row loop, so
this stays O(1) queries regardless of how much data exists (.rule 開發規則
一律非同步 + no N+1)."""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_session
from backend.models.category import Category
from backend.models.chunk import Chunk
from backend.models.document import Document
from backend.models.job import Job
from backend.models.llm_usage import LlmUsage
from backend.models.question import Question
from backend.schemas.stats import StatsOut

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("", response_model=StatsOut)
async def get_stats(session: AsyncSession = Depends(get_session)) -> StatsOut:
    document_status_rows = (
        await session.execute(select(Document.status, func.count()).group_by(Document.status))
    ).all()
    documents_by_status = {status: count for status, count in document_status_rows}

    question_status_rows = (
        await session.execute(select(Question.status, func.count()).group_by(Question.status))
    ).all()
    questions_by_status = {status: count for status, count in question_status_rows}
    chunk_count = (
        await session.execute(select(func.count()).select_from(Chunk))
    ).scalar_one()
    category_count = (
        await session.execute(select(func.count()).select_from(Category))
    ).scalar_one()
    failed_job_count = (
        await session.execute(
            select(func.count()).select_from(Job).where(Job.status == "failed")
        )
    ).scalar_one()

    call_count, prompt_tokens, completion_tokens = (
        await session.execute(
            select(
                func.count(),
                func.coalesce(func.sum(LlmUsage.prompt_tokens), 0),
                func.coalesce(func.sum(LlmUsage.completion_tokens), 0),
            ).select_from(LlmUsage)
        )
    ).one()

    return StatsOut(
        documents_by_status=documents_by_status,
        questions_by_status=questions_by_status,
        chunk_count=chunk_count,
        category_count=category_count,
        failed_job_count=failed_job_count,
        llm_call_count=call_count,
        llm_prompt_tokens=prompt_tokens,
        llm_completion_tokens=completion_tokens,
    )
