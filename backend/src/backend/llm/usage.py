"""`llm_usage` bookkeeping — always called by `backend.llm.client.LLMClient`,
never by job/handler code directly (.rule 開發規則: 每次 LLM 呼叫必須記錄
model 與 token 用量)."""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.models.llm_usage import LlmUsage


async def record_usage(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    model: str,
    purpose: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> None:
    """Insert one `llm_usage` row in its own short-lived session/transaction."""
    async with session_factory() as session:
        session.add(
            LlmUsage(
                model=model,
                purpose=purpose,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )
        )
        await session.commit()
