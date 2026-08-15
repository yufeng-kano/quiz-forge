"""FastAPI application entrypoint.

The lifespan owns the pg-as-queue worker pool (docs/architecture.md 背景任務):
it requeues any job left `running` by a previous crash, starts
`JOB_WORKER_COUNT` asyncio worker coroutines, and cancels them cleanly on
shutdown.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.api.v1 import router as v1_router
from backend.core.config import get_settings
from backend.db.session import AsyncSessionLocal
from backend.jobs import JobWorkerPool


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    worker_pool = JobWorkerPool(
        session_factory=AsyncSessionLocal,
        worker_count=settings.job_worker_count,
        poll_interval_seconds=settings.job_poll_interval_seconds,
    )
    await worker_pool.start()
    app.state.job_worker_pool = worker_pool
    try:
        yield
    finally:
        await worker_pool.stop()


app = FastAPI(title="QuizForge API", lifespan=lifespan)
app.include_router(v1_router)
