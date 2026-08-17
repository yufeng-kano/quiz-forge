"""Worker loop: claim pending jobs with `SELECT ... FOR UPDATE SKIP LOCKED`.

Single-instance deployment (docs/architecture.md — pg-as-queue, no
Celery/Redis; single `backend` container). Crash recovery is therefore
simple: `reset_stale_running_jobs` runs once, before any worker starts
claiming, at FastAPI lifespan startup (see `backend.jobs.service`). In a
single-instance deployment, a job still marked `running` at that point can
only mean the previous process crashed mid-job — nothing else could be
holding it — so it is safe to requeue unconditionally.
"""

import logging

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.jobs.context import JobContext
from backend.jobs.error_summary import UNKNOWN_JOB_KIND, error_for_uncaught
from backend.jobs.registry import get_handler
from backend.models.job import Job

logger = logging.getLogger(__name__)


async def reset_stale_running_jobs(session_factory: async_sessionmaker[AsyncSession]) -> int:
    """Requeue jobs left `running` by a previous process crash. Returns the count."""
    async with session_factory() as session:
        result = await session.execute(
            update(Job)
            .where(Job.status == "running")
            .values(status="pending", error="requeued after backend restart")
            .returning(Job.id)
        )
        requeued_ids = result.scalars().all()
        await session.commit()
        if requeued_ids:
            logger.warning("requeued %d stale running job(s): %s", len(requeued_ids), requeued_ids)
        return len(requeued_ids)


async def claim_job(session: AsyncSession) -> Job | None:
    """Atomically claim the oldest pending job in `session`'s transaction.

    `FOR UPDATE SKIP LOCKED` means concurrent workers polling at the same
    time never see (or block on) a row another worker is already claiming —
    each gets a distinct pending job, or `None` once the queue is empty.
    """
    result = await session.execute(
        select(Job)
        .where(Job.status == "pending")
        .order_by(Job.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    job = result.scalar_one_or_none()
    if job is None:
        return None
    job.status = "running"
    job.error = None
    await session.commit()
    return job


async def run_claimed_job(session_factory: async_sessionmaker[AsyncSession], job_id: int) -> None:
    """Run the handler for an already-claimed (status='running') job.

    Opens its own session so the handler's DB work (including progress
    updates) is independent of whatever session claimed the job. Failures
    are always written to `jobs.error` and leave the job `failed` (retryable
    via `POST /v1/jobs/{id}/retry`) — they are never swallowed.
    """
    async with session_factory() as session:
        job = await session.get(Job, job_id)
        if job is None:
            logger.error("claimed job %d vanished before it could run", job_id)
            return

        handler = get_handler(job.kind)
        if handler is None:
            job.status = "failed"
            job.error = UNKNOWN_JOB_KIND
            await session.commit()
            logger.error("job %d has no handler registered for kind %s", job_id, job.kind)
            return

        ctx = JobContext(job=job, session=session)
        try:
            await handler(ctx)
        except Exception as exc:
            await session.rollback()
            failed_job = await session.get(Job, job_id)
            if failed_job is not None:
                failed_job.status = "failed"
                failed_job.error = error_for_uncaught(exc)
                await session.commit()
            logger.exception("job %d (%s) failed", job_id, job.kind)
            return

        job.status = "done"
        await session.commit()
