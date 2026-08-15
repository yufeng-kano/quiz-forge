"""`GET /v1/jobs/{id}` and `POST /v1/jobs/{id}/retry`.

Frontend polls the former for status/progress/error; the latter is the
minimal-unit retry required by .rule 使用者體驗規則 — it only resets a
*failed* job back to `pending` so a worker picks it up again, it never
re-runs a whole document/batch.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_session
from backend.models.job import Job
from backend.schemas.job import JobOut

router = APIRouter(prefix="/jobs", tags=["jobs"])


async def _get_job_or_404(job_id: int, session: AsyncSession) -> Job:
    job = await session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")
    return job


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
