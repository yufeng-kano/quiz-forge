"""`backend/tests/conftest.py`'s dev-database guard (.rule 反偷懶規則 — job
queue/設定解析屬高風險邏輯需測試；this guard exists specifically because a past
test run truncated the docker-compose dev database).

Two layers of coverage:

1. Direct unit coverage of the predicate (`is_dev_database_url`) across the
   exact cases the guard cares about — db name match, host match, both,
   neither, and a real throwaway URL.
2. An end-to-end subprocess `pytest` run against a fake dev-like
   `DATABASE_URL`, asserting the *whole test session* actually refuses to
   start and prints an explanatory message — proving the `pytest_configure`
   wiring itself works, not just the predicate function in isolation.
"""

import os
import subprocess
from pathlib import Path

from conftest import _ALLOW_DEV_DB_ENV_VAR, is_dev_database_url

_BACKEND_DIR = Path(__file__).resolve().parents[1]


def test_matches_dev_db_name_regardless_of_host() -> None:
    assert is_dev_database_url("postgresql+asyncpg://u:p@localhost:5432/quizforge") is True


def test_matches_compose_service_host_regardless_of_db_name() -> None:
    assert is_dev_database_url("postgresql+asyncpg://u:p@db:5432/some_other_name") is True


def test_matches_when_both_name_and_host_are_the_dev_ones() -> None:
    assert is_dev_database_url("postgresql+asyncpg://u:p@db:5432/quizforge") is True


def test_throwaway_url_is_not_flagged() -> None:
    assert is_dev_database_url("postgresql+asyncpg://u:p@localhost:55432/quizforge_test") is False


def test_similar_but_different_name_and_host_is_not_flagged() -> None:
    assert is_dev_database_url("postgresql+asyncpg://u:p@db2:5432/quizforge2") is False


def test_subprocess_pytest_run_refuses_a_dev_like_database_url() -> None:
    """Runs a nested `pytest` (via `uv run`, per .rule Python 一律用 uv)
    against this same test file, but with `DATABASE_URL` overridden to a
    dev-like URL and no opt-in env var — `pytest_configure` must reject the
    session before collection ever reaches a real database, so this needs
    no throwaway Postgres of its own and stays fast."""
    env = dict(os.environ)
    env["DATABASE_URL"] = "postgresql+asyncpg://quizforge:x@localhost:5432/quizforge"
    env.pop(_ALLOW_DEV_DB_ENV_VAR, None)

    result = subprocess.run(
        ["uv", "run", "pytest", "-q", str(Path(__file__))],
        cwd=_BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )

    combined_output = result.stdout + result.stderr
    assert result.returncode != 0, combined_output
    assert "refusing to run" in combined_output
    assert "DATABASE_URL" in combined_output
    assert "quizforge" in combined_output


def test_subprocess_pytest_run_allows_an_explicit_opt_in() -> None:
    """The same dev-like URL, but with `ALLOW_DEV_DB_TESTS=1` set — the
    guard must step aside (collection then proceeds to actually try
    connecting to that fake database and fails there instead, which is
    exactly the point: the guard's refusal message must be gone)."""
    env = dict(os.environ)
    env["DATABASE_URL"] = "postgresql+asyncpg://quizforge:x@localhost:5432/quizforge"
    env[_ALLOW_DEV_DB_ENV_VAR] = "1"

    result = subprocess.run(
        ["uv", "run", "pytest", "-q", "--collect-only", str(Path(__file__))],
        cwd=_BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )

    combined_output = result.stdout + result.stderr
    assert "refusing to run" not in combined_output, combined_output
