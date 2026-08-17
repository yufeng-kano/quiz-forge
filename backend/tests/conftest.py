"""Shared fixtures.

Tests in this suite run against a real Postgres — point `DATABASE_URL` at a
throwaway database before invoking pytest (see backend/README.md for the
exact commands). Every table a test might write to is truncated before every
test so one test never sees rows left behind by another.

Dev-database guard: a prior test run once truncated the docker-compose dev
database because nothing stopped `DATABASE_URL` from resolving to it. Before
any fixture (in particular `_clean_tables`'s `TRUNCATE`) can run,
`pytest_configure` refuses the whole session when `DATABASE_URL` matches the
compose dev database — its db name (`quizforge`, `POSTGRES_DB` in `.env`) or
its compose-internal service host (`db`) — unless `ALLOW_DEV_DB_TESTS=1` is
explicitly set. `is_dev_database_url` is the predicate this decision boils
down to; it is exercised directly and via a subprocess pytest run in
`test_conftest_dev_db_guard.py`.
"""

import os
from collections.abc import Iterator
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from backend.core.config import get_settings
from backend.db.session import AsyncSessionLocal
from backend.main import app

_DEV_DB_NAME = "quizforge"
_DEV_DB_HOST = "db"
_ALLOW_DEV_DB_ENV_VAR = "ALLOW_DEV_DB_TESTS"


def is_dev_database_url(database_url: str) -> bool:
    """True when `database_url` resolves to the docker-compose dev database:
    same database name as `.env`'s `POSTGRES_DB`/`DATABASE_URL`
    (`quizforge`), or the compose-internal service host (`db`) that
    `DATABASE_URL` points the `backend` container at inside the compose
    network. Either alone is enough — a throwaway test database should use
    neither."""
    parsed = urlsplit(database_url)
    db_name = parsed.path.lstrip("/")
    host = parsed.hostname or ""
    return db_name == _DEV_DB_NAME or host == _DEV_DB_HOST


def pytest_configure(config: pytest.Config) -> None:
    """Runs before test collection and before any fixture — the earliest
    hook pytest offers — so the refusal below happens before `_clean_tables`
    ever gets a chance to `TRUNCATE` anything (see module docstring)."""
    del config  # unused; part of the pytest_configure hook signature
    if os.environ.get(_ALLOW_DEV_DB_ENV_VAR) == "1":
        return
    database_url = get_settings().database_url
    if is_dev_database_url(database_url):
        raise pytest.UsageError(
            "refusing to run the test suite: DATABASE_URL resolves to the docker-compose "
            f"dev database (db name {_DEV_DB_NAME!r} or host {_DEV_DB_HOST!r}). Point "
            "DATABASE_URL at a throwaway database before running tests, or set "
            f"{_ALLOW_DEV_DB_ENV_VAR}=1 to explicitly override this guard."
        )


@pytest.fixture(autouse=True)
async def _clean_tables() -> None:
    async with AsyncSessionLocal() as session:
        await session.execute(
            text(
                "TRUNCATE TABLE jobs, llm_usage, documents, categories, questions, exports, "
                "folders, conversations, conversation_messages RESTART IDENTITY CASCADE"
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
