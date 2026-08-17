"""Question embedding: text flattening + `embed_questions` job handler
(docs/question-bank.md 題目向量化與語意搜尋;
docs/decisions/2026-08-17-bank-agent-semantic-selection.md D1/D2).

Two independent pieces live here:

1. `flatten_question_payload` — turns a stored `(questions.type,
   questions.payload)` pair into the plain text `LLMClient.embed()` embeds.
   Deliberately separate from `backend.export.renderers` (which turns the
   same payload into printable Word prose/tables): the renderer optimizes
   for a human reading a paper exam, this optimizes for a cosine-similarity
   search finding the same question again from a free-text description —
   labelled fields, no formatting markup, one line per fact. It re-validates
   through `backend.questions.schemas.parse_question` first, so a shape
   violation surfaces the same way it would anywhere else in the codebase
   (a `pydantic.ValidationError`), rather than embedding a malformed payload.

2. `embed_questions` — the job handler for job kind `"embed_questions"`,
   payload `{"question_ids": null | [int]}` (docs/question-bank.md).
   `null` means "every question with `embedding IS NULL`" (a one-time
   backfill run); an explicit id list re-embeds exactly those questions,
   regardless of their current embedding state — this is how `POST
   /v1/questions` and `PATCH /v1/questions/{id}` (backend.api.v1.questions)
   pick up a fresh embedding after nulling the stale one out, without ever
   calling the embedding API inline in the request path.

   Questions are embedded `QUESTION_EMBED_BATCH_SIZE` at a time (one
   `LLMClient.embed()` call per batch) but progress is still reported
   per-question ("n/total"), and a single question's failure — not found,
   an unparsable payload, or the batch's embedding call itself erroring —
   is recorded in the job's failure summary without aborting any other
   question, in *any other batch or this one* (.rule 反偷懶規則 — 禁止部分處理／
   最小單位可重試). Only when *every* targeted question failed does the job
   end `failed` (mirrors `backend.questions.generation.generate_questions`
   and `backend.export.job.export_docx`'s per-item failure handling).
"""

import logging

from sqlalchemy import select

from backend.core.config import get_settings
from backend.jobs.context import JobContext
from backend.jobs.error_summary import (
    EMBED_MISSING,
    EMBED_UNPARSABLE,
    JOB_FAILED,
    JobFailed,
    summarize_embedding_failures,
)
from backend.jobs.registry import register_handler
from backend.llm.client import get_llm_client
from backend.models.question import Question
from backend.questions.schemas import (
    AnalogyQuestion,
    ComparisonQuestion,
    FillBlankQuestion,
    QuestionModel,
    ShortAnswerQuestion,
    SingleChoiceQuestion,
    TrueFalseQuestion,
    parse_question,
)

logger = logging.getLogger(__name__)

# `embed_questions`'s own write-time purpose, mirroring `chunks.embedding`'s
# `embed_chunk` (backend.ingestion.pipeline) — distinct from the read-time
# `question_search` purpose `GET /v1/questions`'s `similar_to` uses to embed
# the caller's free-text query (docs/question-bank.md), so `llm_usage` can
# tell "backfilling the bank" apart from "one search query" in the usage page.
EMBED_QUESTION_PURPOSE = "embed_question"


def _non_empty_lines(*parts: str | None) -> list[str]:
    return [part for part in parts if part]


def _flatten(question: QuestionModel) -> str:
    """One line per non-empty fact in `question`, covering every one of the
    six types (docs/question-bank.md 題目向量化與語意搜尋 — 題幹、選項、答案、
    解析；比較題另含 A/B 主體與面向，類比題含四個槽位)."""
    if isinstance(question, ComparisonQuestion):
        lines = _non_empty_lines(
            question.stem,
            f"主體A：{question.subject_a}",
            f"主體B：{question.subject_b}",
            "比較面向：" + "、".join(question.aspects),
        )
        lines.extend(f"相同點：{item}" for item in question.model_answer.similarities)
        lines.extend(
            f"差異（{diff.aspect}）：A={diff.a}；B={diff.b}"
            for diff in question.model_answer.differences
        )
        return "\n".join(lines)

    if isinstance(question, AnalogyQuestion):
        lines = _non_empty_lines(
            f"A：{question.a}",
            f"B：{question.b}",
            f"C：{question.c}",
            f"答案：{question.answer}",
            question.explanation,
        )
        if question.options:
            lines.append("選項：" + "、".join(question.options))
        return "\n".join(lines)

    if isinstance(question, SingleChoiceQuestion):
        lines = _non_empty_lines(
            question.stem,
            "選項：" + "、".join(question.options),
            f"答案：{question.options[question.answer_index]}",
            question.explanation,
        )
        return "\n".join(lines)

    if isinstance(question, TrueFalseQuestion):
        lines = _non_empty_lines(
            question.stem,
            f"答案：{'正確' if question.answer else '錯誤'}",
            question.explanation,
        )
        return "\n".join(lines)

    if isinstance(question, FillBlankQuestion):
        lines = _non_empty_lines(question.stem, "答案：" + "、".join(question.answers))
        return "\n".join(lines)

    if isinstance(question, ShortAnswerQuestion):
        lines = _non_empty_lines(question.stem, f"答案：{question.model_answer}")
        lines.extend(f"重點：{point}" for point in question.key_points)
        return "\n".join(lines)

    # `QuestionModel` is a closed 6-member union and every member is handled
    # above -- this is unreachable by construction. It stays as a loud
    # failure (not `assert_never`) so an eventual 7th question type shows up
    # as "unsupported" here instead of silently falling through to empty text.
    raise ValueError(f"unsupported question type: {type(question).__name__}")


def flatten_question_payload(question_type: str, payload: dict[str, object]) -> str:
    """The text embedded for a `(questions.type, questions.payload)` pair.
    Re-validates `payload` through `parse_question` first — the exact same
    discriminated-union validation the API and `generate_questions` already
    apply, so a shape violation raises `pydantic.ValidationError` here too
    rather than embedding garbage."""
    return _flatten(parse_question(question_type, payload))


def _parse_target_ids(payload: dict[str, object]) -> list[int] | None:
    """`payload["question_ids"]` — `None` means "every `embedding IS NULL`
    question" (resolved by the caller); otherwise a de-duplicated,
    order-preserving `list[int]`."""
    value = payload.get("question_ids")
    if value is None:
        return None
    if not isinstance(value, list):
        raise ValueError(f"job payload field 'question_ids' must be a list or null: {payload!r}")
    ids: list[int] = []
    for item in value:
        if not isinstance(item, int) or isinstance(item, bool):
            raise ValueError(
                f"job payload field 'question_ids' must be a list of integers: {payload!r}"
            )
        ids.append(item)
    seen: set[int] = set()
    ordered: list[int] = []
    for question_id in ids:
        if question_id not in seen:
            seen.add(question_id)
            ordered.append(question_id)
    return ordered


async def _resolve_target_ids(ctx: JobContext) -> list[int]:
    explicit_ids = _parse_target_ids(ctx.payload)
    if explicit_ids is not None:
        return explicit_ids
    rows = await ctx.session.execute(
        select(Question.id).where(Question.embedding.is_(None)).order_by(Question.id)
    )
    return list(rows.scalars().all())


@register_handler("embed_questions")
async def embed_questions(ctx: JobContext) -> None:
    settings = get_settings()
    llm = get_llm_client()
    session = ctx.session

    target_ids = await _resolve_target_ids(ctx)
    total = len(target_ids)
    await ctx.set_progress(f"0/{total}")
    if total == 0:
        return

    batch_size = settings.question_embed_batch_size
    index = 0
    success = 0
    failure_reasons: list[str | None] = []

    for batch_start in range(0, total, batch_size):
        batch_ids = target_ids[batch_start : batch_start + batch_size]
        rows = (
            (await session.execute(select(Question).where(Question.id.in_(batch_ids))))
            .scalars()
            .all()
        )
        by_id = {row.id: row for row in rows}

        texts: list[str] = []
        embeddable: list[Question] = []
        for question_id in batch_ids:
            question = by_id.get(question_id)
            if question is None:
                index += 1
                failure_reasons.append(EMBED_MISSING)
                await ctx.set_progress(f"{index}/{total}")
                continue
            try:
                texts.append(flatten_question_payload(question.type, question.payload))
                embeddable.append(question)
            except Exception:
                index += 1
                logger.exception(
                    "question %d (type=%s) payload failed to flatten for embedding",
                    question_id,
                    question.type,
                )
                failure_reasons.append(EMBED_UNPARSABLE)
                await ctx.set_progress(f"{index}/{total}")

        if not embeddable:
            continue

        try:
            embeddings = await llm.embed(texts=texts, purpose=EMBED_QUESTION_PURPOSE)
        except Exception:
            logger.exception("embedding batch of %d question(s) failed", len(embeddable))
            for _ in embeddable:
                index += 1
                failure_reasons.append(None)
                await ctx.set_progress(f"{index}/{total}")
            continue

        for question, embedding in zip(embeddable, embeddings, strict=True):
            question.embedding = embedding
            index += 1
            success += 1
            await ctx.set_progress(f"{index}/{total}")

    if failure_reasons:
        ctx.job.error = summarize_embedding_failures(failure_reasons)

    if success == 0:
        raise JobFailed(ctx.job.error or JOB_FAILED)
