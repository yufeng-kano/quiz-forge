"""Async SQLAlchemy engine and session factory."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from backend.core.config import get_settings

settings = get_settings()

# NullPool: single-user local deployment (docs/architecture.md — 單人資料量小)
# has no need for a persistent connection pool, and a pooled asyncpg
# connection cannot be reused once the asyncio event loop that first
# checked it out is gone (e.g. FastAPI's TestClient opens a fresh loop per
# `with TestClient(app) as client:` block) — NullPool opens/closes a plain
# connection per checkout instead, so the engine works from any loop.
engine = create_async_engine(settings.database_url, poolclass=NullPool)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncGenerator[AsyncSession]:
    """FastAPI dependency yielding a request-scoped async DB session."""
    async with AsyncSessionLocal() as session:
        yield session
