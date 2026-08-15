"""Application settings.

All environment-dependent values (LLM 供應商設定、資料庫連線、資料目錄等) come from
the project-root `.env` file — never hardcoded here. See `docs/architecture.md`
for the authoritative variable list.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# repo-root/.env — this file lives at backend/src/backend/core/config.py,
# so four `.parent` hops land on the repo root regardless of cwd.
_REPO_ROOT_ENV = Path(__file__).resolve().parents[4] / ".env"


class Settings(BaseSettings):
    """Settings sourced from process environment / project-root `.env`.

    In Docker, docker-compose's `env_file` already injects these as real
    process environment variables. Reading `_REPO_ROOT_ENV` is only a
    convenience for running the backend directly on the host with `uv run`.
    """

    model_config = SettingsConfigDict(
        env_file=_REPO_ROOT_ENV,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM（OpenAI-compatible，預設 OpenRouter）
    llm_base_url: str = "https://openrouter.ai/api/v1"
    llm_api_key: str = ""
    vision_model: str = "google/gemini-3.6-flash"
    text_model: str = "openai/gpt-5.6-luna"
    embedding_model: str = "openai/text-embedding-3-small"
    embedding_dim: int = 1536
    llm_concurrency: int = 4
    ocr_dpi: int = 200

    # 文件解析／chunk（docs/ingestion.md — chunk 依標題結構＋長度上限切分）
    chunk_max_chars: int = 4000

    # 背景任務（pg-as-queue，見 docs/architecture.md）
    job_worker_count: int = 2
    job_poll_interval_seconds: float = 1.0

    # 出題：比較題配對用的 cosine 相似度中間帶（docs/question-bank.md —
    # 「相關但不相同」）。低於 min 視為不相關，高於 max 視為幾乎重複。
    comparison_similarity_min: float = 0.35
    comparison_similarity_max: float = 0.75

    # 基礎設施
    database_url: str = "postgresql+asyncpg://quizforge:quizforge@localhost:5432/quizforge"
    data_dir: Path = Path("/data")

    # backend 服務自身監聽設定（container 內部，供 entrypoint 讀取）
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
