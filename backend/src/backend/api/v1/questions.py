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

`GET /v1/questions` also paginates (`limit`/`offset`, envelope with `total`)
and full-text-ish searches (`q`, case-insensitive `ILIKE` against
`payload::text` — docs/question-bank.md `q` 全文搜尋). `limit`'s default and
max come from `Settings` (never hardcoded, per .rule 開發規則), not a
`Query(...)` default — that would freeze the value at *import* time,
whereas settings can change per-request in tests (env + `get_settings.
cache_clear()`) exactly like every other settings-driven handler in this
codebase (e.g. `backend.ingestion.pipeline`).

`similar_to` (docs/question-bank.md 題目向量化與語意搜尋;
docs/decisions/2026-08-17-bank-agent-semantic-selection.md D3) layers
semantic ranking on top of every filter above rather than replacing them:
the free text is embedded once (purpose `question_search`), rows with a
`NULL` embedding or a cosine similarity below `QUESTION_SIMILARITY_MIN` are
dropped, and the rest are ordered by similarity descending. `q` (if also
given) still applies as a literal `ILIKE` hard filter first — `similar_to`
only changes ordering and the similarity floor. The actual query lives in
`backend.questions.search.search_questions`, not here: `GET /v1/questions`
and the bank-agent's `action="search"` step
(`backend.questions.agent.bank_agent_turn`) both call that one function, so
a manual filter here and the agent's search can never drift apart (D3).
`unembedded_total` is computed once from the filters above `similar_to`
itself, so it is meaningful whether or not `similar_to` was given at all.

Both `POST /v1/questions` and `PATCH /v1/questions/{id}` (when `payload` is
actually part of the request) null out `embedding` and enqueue a
single-question `embed_questions` job rather than calling the embedding API
inline — docs/question-bank.md 題目向量化與語意搜尋: 「不讓 embedding 延遲或
失敗擋住編輯」.
"""

import json

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import get_settings
from backend.db.session import get_session
from backend.llm.client import get_llm_client
from backend.models.chunk import Chunk
from backend.models.job import Job
from backend.models.question import Question
from backend.questions.schemas import dump_payload, parse_question
from backend.questions.search import search_questions
from backend.schemas.question import (
    EmbedQuestionsIn,
    EmbedQuestionsOut,
    QuestionCreateIn,
    QuestionDetailOut,
    QuestionListItemOut,
    QuestionListOut,
    QuestionPatchIn,
    SourceChunkOut,
)

router = APIRouter(prefix="/questions", tags=["questions"])


async def _enqueue_embed_job(session: AsyncSession, question_id: int) -> None:
    """Queues a single-question `embed_questions` job — the only way
    `embedding` ever gets (re)computed from the request path, so a slow or
    failing embedding call never blocks `POST`/`PATCH` (docs/question-bank.md
    題目向量化與語意搜尋)."""
    session.add(Job(kind="embed_questions", payload={"question_ids": [question_id]}))
    await session.commit()


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


@router.get("", response_model=QuestionListOut)
async def list_questions(
    status_filter: str | None = Query(None, alias="status"),
    type_filter: str | None = Query(None, alias="type"),
    category_id: int | None = Query(None),
    difficulty: str | None = Query(None),
    q: str | None = Query(None, description="payload::text 的大小寫不敏感 ILIKE 搜尋"),
    similar_to: str | None = Query(
        None, description="語意搜尋自由文字；embed 一次後以 cosine 相似度排序＋門檻過濾"
    ),
    limit: int | None = Query(None, ge=1),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> QuestionListOut:
    settings = get_settings()
    if limit is not None and limit > settings.questions_list_limit_max:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"limit must be <= {settings.questions_list_limit_max}",
        )
    effective_limit = limit if limit is not None else settings.questions_list_limit_default

    result = await search_questions(
        session,
        settings,
        get_llm_client(),
        status=status_filter,
        type=type_filter,
        difficulty=difficulty,
        category_id=category_id,
        q=q,
        similar_to=similar_to,
        limit=effective_limit,
        offset=offset,
    )
    return QuestionListOut(
        items=[_to_list_item(question) for question in result.items],
        total=result.total,
        limit=effective_limit,
        offset=offset,
        unembedded_total=result.unembedded_total,
    )


@router.post("/embed", response_model=EmbedQuestionsOut, status_code=status.HTTP_201_CREATED)
async def create_embed_job(
    body: EmbedQuestionsIn, session: AsyncSession = Depends(get_session)
) -> EmbedQuestionsOut:
    """Enqueues an `embed_questions` job (docs/question-bank.md 相關 API) —
    `question_ids=null` backfills every `embedding IS NULL` question,
    otherwise re-embeds exactly the given ids."""
    job = Job(kind="embed_questions", payload={"question_ids": body.question_ids})
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return EmbedQuestionsOut(job_id=job.id)


@router.post("", response_model=QuestionListItemOut, status_code=status.HTTP_201_CREATED)
async def create_question(
    body: QuestionCreateIn, session: AsyncSession = Depends(get_session)
) -> QuestionListItemOut:
    """Manual question authoring (docs/question-bank.md 手動建題) — `payload`
    goes through the exact same discriminated-union validation as LLM
    output and `PATCH`, so a shape violation is a 422 regardless of who
    wrote the JSON. `source_chunk_ids` is always empty: a hand-written
    question has no generation source to trace back to."""
    try:
        validated = parse_question(body.type, body.payload)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=json.loads(exc.json())
        ) from exc

    question = Question(
        type=body.type,
        difficulty=body.difficulty,
        status=body.status,
        payload=dump_payload(validated),
        source_chunk_ids=[],
    )
    session.add(question)
    await session.commit()
    await session.refresh(question)
    await _enqueue_embed_job(session, question.id)
    return _to_list_item(question)


@router.post(
    "/{question_id}/duplicate",
    response_model=QuestionListItemOut,
    status_code=status.HTTP_201_CREATED,
)
async def duplicate_question(
    question_id: int, session: AsyncSession = Depends(get_session)
) -> QuestionListItemOut:
    """Copy an existing question as a new `draft` (docs/question-bank.md
    複製為 draft 改造變體) — same `type`/`difficulty`/`payload`/
    `source_chunk_ids` as the original, so the copy still traces back to
    whatever generated the original before it gets edited into a variant."""
    original = await _get_question_or_404(question_id, session)
    duplicate = Question(
        type=original.type,
        difficulty=original.difficulty,
        status="draft",
        payload=original.payload,
        source_chunk_ids=list(original.source_chunk_ids),
    )
    session.add(duplicate)
    await session.commit()
    await session.refresh(duplicate)
    return _to_list_item(duplicate)


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
        # 有動到 payload 時 (docs/question-bank.md 題目向量化與語意搜尋): the old
        # embedding no longer describes this question, so it is invalidated
        # immediately and a background job recomputes it — never an inline
        # embedding call in this request path.
        question.embedding = None

    if "difficulty" in provided:
        question.difficulty = body.difficulty

    await session.commit()
    await session.refresh(question)
    if "payload" in provided:
        await _enqueue_embed_job(session, question.id)
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
