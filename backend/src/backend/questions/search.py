"""Shared question-search query path (docs/question-bank.md 題目向量化與語意
搜尋; docs/decisions/2026-08-17-bank-agent-semantic-selection.md D3).

`search_questions` is the *one* place the `status`/`type`/`difficulty`/
`category_id`/`q`/`similar_to` filter set turns into a SQL query. Both
`GET /v1/questions` (`backend.api.v1.questions`) and the bank-agent's
`action="search"` step (`backend.questions.agent`) call this exact function
— D3 requires it explicitly ("選題助手和使用者手動篩選要走同一條查詢路徑，
否則兩邊行為會漂移"), so a manual filter on the questions page and the
agent's search always behave identically by construction, not by convention.
"""

from dataclasses import dataclass

from sqlalchemy import String, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import Settings
from backend.llm.client import LLMClient
from backend.models.chunk import Chunk
from backend.models.question import Question


@dataclass
class QuestionSearchResult:
    """One `search_questions` call's result: the page of matching rows plus
    the two counts `GET /v1/questions`'s pagination envelope needs (`total`,
    `unembedded_total`)."""

    items: list[Question]
    total: int
    unembedded_total: int


async def search_questions(
    session: AsyncSession,
    settings: Settings,
    llm: LLMClient,
    *,
    status: str | None = None,
    type: str | None = None,
    difficulty: str | None = None,
    category_id: int | None = None,
    q: str | None = None,
    similar_to: str | None = None,
    limit: int,
    offset: int = 0,
) -> QuestionSearchResult:
    """Run the shared question query.

    `llm` is only actually called (one `embed()`, purpose `question_search`)
    when `similar_to` is given — callers always pass a real `LLMClient`
    (mirroring `backend.questions.generation.generate_questions`'s
    `llm = get_llm_client()` at the top of the handler, used or not
    depending on which branch runs) so a fake client in tests observes
    every embed call it should and none it shouldn't.
    """
    stmt = select(Question)
    if status is not None:
        stmt = stmt.where(Question.status == status)
    if type is not None:
        stmt = stmt.where(Question.type == type)
    if difficulty is not None:
        stmt = stmt.where(Question.difficulty == difficulty)
    if category_id is not None:
        chunk_ids = (
            (await session.execute(select(Chunk.id).where(Chunk.category_id == category_id)))
            .scalars()
            .all()
        )
        if not chunk_ids:
            return QuestionSearchResult(items=[], total=0, unembedded_total=0)
        # `questions.source_chunk_ids` is a plain `sqlalchemy.ARRAY`, whose
        # comparator (unlike `dialects.postgresql.ARRAY`) has no `.overlap()`
        # helper — `.op("&&")` sends Postgres's own array-overlap operator
        # directly, coerced against the column's `ARRAY(Integer)` type.
        stmt = stmt.where(Question.source_chunk_ids.op("&&")(list(chunk_ids)))
    if q:
        stmt = stmt.where(cast(Question.payload, String).ilike(f"%{q}%"))

    # `unembedded_total` reads only the filters built above `similar_to`
    # itself (docs/question-bank.md 題目向量化與語意搜尋) — it must stay
    # meaningful even when `similar_to` was not given at all.
    unembedded_total = (
        await session.execute(
            select(func.count()).select_from(
                stmt.where(Question.embedding.is_(None)).subquery()
            )
        )
    ).scalar_one()

    if similar_to:
        [query_vector] = await llm.embed(texts=[similar_to], purpose="question_search")
        similarity = (1 - Question.embedding.cosine_distance(query_vector)).label("similarity")
        stmt = stmt.where(Question.embedding.is_not(None)).where(
            similarity >= settings.question_similarity_min
        )
        order_by = (similarity.desc(), Question.id.desc())
    else:
        order_by = (Question.created_at.desc(), Question.id.desc())

    total = (
        await session.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()

    list_stmt = stmt.order_by(*order_by).limit(limit).offset(offset)
    questions = (await session.execute(list_stmt)).scalars().all()
    return QuestionSearchResult(
        items=list(questions), total=total, unembedded_total=unembedded_total
    )
