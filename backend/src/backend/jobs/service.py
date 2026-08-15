"""Startup/shutdown wiring for the job worker pool — used by the FastAPI lifespan.

`JobWorkerPool.start()` requeues stale `running` jobs once, then launches N
asyncio worker tasks that each poll `jobs` on their own interval. `stop()`
cancels every task and waits for them to unwind cleanly, so a shutdown never
leaves a claim half-committed.
"""

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.jobs.worker import claim_job, reset_stale_running_jobs, run_claimed_job

logger = logging.getLogger(__name__)


async def _worker_loop(
    worker_id: int,
    session_factory: async_sessionmaker[AsyncSession],
    poll_interval_seconds: float,
) -> None:
    logger.info("job worker %d started", worker_id)
    try:
        while True:
            async with session_factory() as session:
                job = await claim_job(session)
            if job is None:
                await asyncio.sleep(poll_interval_seconds)
                continue
            await run_claimed_job(session_factory, job.id)
    except asyncio.CancelledError:
        logger.info("job worker %d cancelled", worker_id)
        raise


class JobWorkerPool:
    """Owns the N asyncio worker tasks started by the FastAPI lifespan."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        worker_count: int,
        poll_interval_seconds: float,
    ) -> None:
        self._session_factory = session_factory
        self._worker_count = worker_count
        self._poll_interval_seconds = poll_interval_seconds
        self._tasks: list[asyncio.Task[None]] = []

    async def start(self) -> None:
        await reset_stale_running_jobs(self._session_factory)
        self._tasks = [
            asyncio.create_task(
                _worker_loop(worker_id, self._session_factory, self._poll_interval_seconds),
                name=f"job-worker-{worker_id}",
            )
            for worker_id in range(self._worker_count)
        ]
        logger.info("started %d job worker(s)", self._worker_count)

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks = []
        logger.info("stopped job worker(s)")
