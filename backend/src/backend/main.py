"""FastAPI application entrypoint.

The lifespan owns the pg-as-queue worker pool (docs/architecture.md 背景任務):
it requeues any job left `running` by a previous crash, starts
`JOB_WORKER_COUNT` asyncio worker coroutines, and cancels them cleanly on
shutdown.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.api.v1 import router as v1_router
from backend.core.config import get_settings
from backend.db.session import AsyncSessionLocal
from backend.export.job import export_docx
from backend.ingestion.pipeline import parse_document, parse_page, rechunk_document
from backend.jobs import JobWorkerPool, registered_kinds
from backend.questions.agent import bank_agent_turn
from backend.questions.embedding import embed_questions
from backend.questions.generation import generate_questions

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    # Importing `backend.ingestion.pipeline`/`backend.questions.generation`/
    # `backend.export.job` above registers their job handlers (the
    # `@register_handler` decorator runs at import time) — referenced here
    # so a worker pool never starts without them, and confirmed in the
    # startup log.
    logger.info(
        "job handlers loaded: %s, %s, %s, %s, %s, %s, %s -- registered job kinds: %s",
        parse_document.__name__,
        parse_page.__name__,
        rechunk_document.__name__,
        generate_questions.__name__,
        export_docx.__name__,
        embed_questions.__name__,
        bank_agent_turn.__name__,
        registered_kinds(),
    )
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
