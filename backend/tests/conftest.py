"""Shared fixtures.

Tests in this suite run against a real Postgres — point `DATABASE_URL` at a
throwaway database before invoking pytest (see backend/README.md for the
exact commands). Every table a test might write to is truncated before every
test so one test never sees rows left behind by another.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from backend.core.config import get_settings
from backend.db.session import AsyncSessionLocal
from backend.main import app


@pytest.fixture(autouse=True)
async def _clean_tables() -> None:
    async with AsyncSessionLocal() as session:
        await session.execute(
            text(
                "TRUNCATE TABLE jobs, llm_usage, documents, categories, questions, exports "
                "RESTART IDENTITY CASCADE"
            )
        )
        await session.commit()


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """`TestClient` with the background worker pool disabled.

    API tests set up job rows directly via `tests.factories`, so a live
    worker racing to claim/run them would make those tests flaky. The
    worker loop itself is exercised for real in `test_jobs_queue.py`.
    """
    monkeypatch.setenv("JOB_WORKER_COUNT", "0")
    get_settings.cache_clear()
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        get_settings.cache_clear()
