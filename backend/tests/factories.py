"""Test-only helpers for inserting rows directly, bypassing the API/queue —
used to set up preconditions ("a job that is already `failed`", ...)."""

from backend.db.session import AsyncSessionLocal
from backend.models.job import Job
from backend.models.llm_usage import LlmUsage


async def create_job(
    kind: str,
    *,
    status: str = "pending",
    progress: str = "",
    error: str | None = None,
    retry_count: int = 0,
    payload: dict[str, object] | None = None,
) -> int:
    async with AsyncSessionLocal() as session:
        job = Job(
            kind=kind,
            payload=payload or {},
            status=status,
            progress=progress,
            error=error,
            retry_count=retry_count,
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)
        return job.id


async def create_llm_usage(
    *, model: str, purpose: str, prompt_tokens: int, completion_tokens: int
) -> int:
    async with AsyncSessionLocal() as session:
        row = LlmUsage(
            model=model,
            purpose=purpose,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return row.id
