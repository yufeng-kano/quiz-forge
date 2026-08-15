"""`/v1/questions` — review queue + question-bank browsing (docs/question-bank.md 審題流程).

Status state machine (only `draft`/`approved`/`rejected` exist, enforced by
the `ck_questions_status` CHECK constraint):

- `POST /approve`: `draft -> approved` only. Approving is the final quality
  gate (docs/question-bank.md — LLM 出題必有爛題，須人工把關), so it is
  reachable only from a fresh, never-yet-decided draft; anything else is a
  409.
- `POST /reject`: `draft -> rejected`, `approved -> rejected` (discard at
  any point before/after adoption), and `rejected -> draft` (undo — a second
  「丟棄」click on an already-rejected question restores it to draft so it
  can be edited and re-reviewed rather than staying stuck rejected forever).
  Every one of the three possible statuses has a defined `reject` outcome,
  so this endpoint never 409s.

`GET /v1/questions` filters on `category` indirectly: a question has no
`category_id` of its own, so filtering by category means "has at least one
source chunk in that category" (`source_chunk_ids` array-overlap against
that category's chunk ids).
"""

import json

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_session
from backend.models.chunk import Chunk
from backend.models.question import Question
from backend.questions.schemas import dump_payload, parse_question
from backend.schemas.question import (
    QuestionDetailOut,
    QuestionListItemOut,
    QuestionPatchIn,
    SourceChunkOut,
)

router = APIRouter(prefix="/questions", tags=["questions"])


def _to_list_item(question: Question) -> QuestionListItemOut:
    return QuestionListItemOut(
        id=question.id,
        type=question.type,
        difficulty=question.difficulty,
        status=question.status,
        payload=question.payload,
        source_chunk_ids=question.source_chunk_ids,
        created_at=question.created_at,
    )


async def _get_question_or_404(question_id: int, session: AsyncSession) -> Question:
    question = await session.get(Question, question_id)
    if question is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="question not found")
    return question


@router.get("", response_model=list[QuestionListItemOut])
async def list_questions(
    status_filter: str | None = Query(None, alias="status"),
    type_filter: str | None = Query(None, alias="type"),
    category_id: int | None = Query(None),
    difficulty: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
) -> list[QuestionListItemOut]:
    stmt = select(Question)
    if status_filter is not None:
        stmt = stmt.where(Question.status == status_filter)
    if type_filter is not None:
        stmt = stmt.where(Question.type == type_filter)
    if difficulty is not None:
        stmt = stmt.where(Question.difficulty == difficulty)
    if category_id is not None:
        chunk_ids = (
            (await session.execute(select(Chunk.id).where(Chunk.category_id == category_id)))
            .scalars()
            .all()
        )
        if not chunk_ids:
            return []
        # `questions.source_chunk_ids` is a plain `sqlalchemy.ARRAY`, whose
        # comparator (unlike `dialects.postgresql.ARRAY`) has no `.overlap()`
        # helper — `.op("&&")` sends Postgres's own array-overlap operator
        # directly, coerced against the column's `ARRAY(Integer)` type.
        stmt = stmt.where(Question.source_chunk_ids.op("&&")(list(chunk_ids)))
    stmt = stmt.order_by(Question.created_at.desc(), Question.id.desc())

    questions = (await session.execute(stmt)).scalars().all()
    return [_to_list_item(question) for question in questions]


@router.get("/{question_id}", response_model=QuestionDetailOut)
async def get_question(
    question_id: int, session: AsyncSession = Depends(get_session)
) -> QuestionDetailOut:
    """Detail including full source-chunk text, so the review page can
    compare a drafted question against the 原文 it was generated from."""
    question = await _get_question_or_404(question_id, session)
    chunks = (
        (await session.execute(select(Chunk).where(Chunk.id.in_(question.source_chunk_ids))))
        .scalars()
        .all()
    )
    chunks_by_id = {chunk.id: chunk for chunk in chunks}
    source_chunks = [
        SourceChunkOut(id=chunk_id, content=chunks_by_id[chunk_id].content)
        for chunk_id in question.source_chunk_ids
        if chunk_id in chunks_by_id
    ]
    return QuestionDetailOut(
        **_to_list_item(question).model_dump(), source_chunks=source_chunks
    )


@router.patch("/{question_id}", response_model=QuestionListItemOut)
async def patch_question(
    question_id: int, body: QuestionPatchIn, session: AsyncSession = Depends(get_session)
) -> QuestionListItemOut:
    """Edit payload and/or difficulty. `payload` is re-validated through the
    same discriminated-union model that validates LLM output, so a shape
    violation (missing field, `answer_index` out of range, mismatched
    `fill_blank` blank count, ...) is rejected with 422 the same way
    regardless of who produced the JSON."""
    question = await _get_question_or_404(question_id, session)
    provided = body.model_fields_set

    if "payload" in provided:
        if body.payload is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="payload cannot be null",
            )
        try:
            validated = parse_question(question.type, body.payload)
        except ValidationError as exc:
            # `exc.errors()` includes a `ctx` entry with the raw Python
            # exception object for custom validators — not JSON-serializable
            # as-is, so go through `exc.json()` (pydantic's own JSON-safe
            # serialization) instead of hand-picking which fields to keep.
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=json.loads(exc.json())
            ) from exc
        question.payload = dump_payload(validated)

    if "difficulty" in provided:
        question.difficulty = body.difficulty

    await session.commit()
    await session.refresh(question)
    return _to_list_item(question)


@router.post("/{question_id}/approve", response_model=QuestionListItemOut)
async def approve_question(
    question_id: int, session: AsyncSession = Depends(get_session)
) -> QuestionListItemOut:
    question = await _get_question_or_404(question_id, session)
    if question.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"question {question_id} is {question.status!r}; only a draft can be approved",
        )
    question.status = "approved"
    await session.commit()
    await session.refresh(question)
    return _to_list_item(question)


@router.post("/{question_id}/reject", response_model=QuestionListItemOut)
async def reject_question(
    question_id: int, session: AsyncSession = Depends(get_session)
) -> QuestionListItemOut:
    question = await _get_question_or_404(question_id, session)
    question.status = "draft" if question.status == "rejected" else "rejected"
    await session.commit()
    await session.refresh(question)
    return _to_list_item(question)


@router.delete("/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_question(question_id: int, session: AsyncSession = Depends(get_session)) -> None:
    question = await _get_question_or_404(question_id, session)
    await session.delete(question)
    await session.commit()
