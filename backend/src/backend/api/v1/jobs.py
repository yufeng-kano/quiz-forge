"""`GET /v1/jobs`, `GET /v1/jobs/{id}` and `POST /v1/jobs/{id}/retry`.

Frontend polls the singular route for status/progress/error; the list route
backs the 任務中心 overview (docs/decisions/2026-08-15-ux-overhaul-feature-
expansion.md F5 — 任務列表：篩 status/kind、新到舊、limit). `retry` is the
minimal-unit retry required by .rule 使用者體驗規則 — it only resets a
*failed* job back to `pending` so a worker picks it up again, it never
re-runs a whole document/batch.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import get_settings
from backend.db.session import get_session
from backend.models.job import Job
from backend.schemas.job import JobOut

router = APIRouter(prefix="/jobs", tags=["jobs"])


async def _get_job_or_404(job_id: int, session: AsyncSession) -> Job:
    job = await session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")
    return job


@router.get("", response_model=list[JobOut])
async def list_jobs(
    status_filter: str | None = Query(None, alias="status"),
    kind: str | None = Query(None),
    limit: int | None = Query(None, ge=1),
    session: AsyncSession = Depends(get_session),
) -> list[Job]:
    """Newest first; `limit`'s default/max come from `Settings` (never
    hardcoded), matching `GET /v1/questions`'s pagination convention."""
    settings = get_settings()
    if limit is not None and limit > settings.jobs_list_limit_max:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"limit must be <= {settings.jobs_list_limit_max}",
        )
    effective_limit = limit if limit is not None else settings.jobs_list_limit_default

    stmt = select(Job)
    if status_filter is not None:
        stmt = stmt.where(Job.status == status_filter)
    if kind is not None:
        stmt = stmt.where(Job.kind == kind)
    stmt = stmt.order_by(Job.created_at.desc(), Job.id.desc()).limit(effective_limit)

    return list((await session.execute(stmt)).scalars().all())


@router.get("/{job_id}", response_model=JobOut)
async def get_job(job_id: int, session: AsyncSession = Depends(get_session)) -> Job:
    """Current status/progress/error for polling clients."""
    return await _get_job_or_404(job_id, session)


@router.post("/{job_id}/retry", response_model=JobOut)
async def retry_job(job_id: int, session: AsyncSession = Depends(get_session)) -> Job:
    """Reset a `failed` job to `pending` so a worker re-claims it.

    Only `failed` jobs can be retried — retrying a `pending`/`running`/`done`
    job would either be a no-op or silently discard a result, so both are
    rejected with 409 instead.
    """
    job = await _get_job_or_404(job_id, session)
    if job.status != "failed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"job {job_id} is {job.status!r}; only a failed job can be retried",
        )
    job.status = "pending"
    job.error = None
    job.retry_count += 1
    job.progress = ""
    await session.commit()
    await session.refresh(job)
    return job
