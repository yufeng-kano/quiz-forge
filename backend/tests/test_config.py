"""Settings parsing — defaults and env-var overrides.

Both tests disable the repo-root `.env` lookup so they never depend on
whatever happens to be on disk locally: `monkeypatch.setitem` flips the
`env_file` entry of `Settings.model_config` (a plain mutable mapping) off
for the duration of the test, restoring it automatically afterwards. This
avoids passing pydantic-settings' `_env_file=...` init kwarg directly,
which basedpyright's synthesized-`__init__` view of `BaseSettings` doesn't
recognize even though it works at runtime.
"""

import pytest

from backend.core.config import Settings


@pytest.fixture(autouse=True)
def _no_dotenv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(Settings.model_config, "env_file", None)


def test_settings_defaults() -> None:
    settings = Settings()
    assert settings.embedding_dim == 1536
    assert settings.llm_concurrency == 4
    assert settings.ocr_dpi == 200


def test_settings_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EMBEDDING_DIM", "768")
    monkeypatch.setenv("LLM_CONCURRENCY", "8")
    settings = Settings()
    assert settings.embedding_dim == 768
    assert settings.llm_concurrency == 8
