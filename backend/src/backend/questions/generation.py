"""`generate_questions` job handler (docs/question-bank.md 出題流程).

Wires `backend.questions.selection` (which chunk(s) feed each question) to
`backend.questions.prompts` (what to ask) and `backend.llm.client.LLMClient`
(the actual `TEXT_MODEL` call, `response_format: json_schema` of the
specific type's Pydantic model). Every generated question is stored
`status="draft"` immediately.

Failure handling (.rule 反偷懶規則 — 禁止吞例外／禁止部分處理；docs/question-bank.md —
生成一律逐題進行): one question's generation failure is caught, logged in
full, and recorded in the job's final error summary — it never aborts the
remaining questions. The job only ends up `failed` (raises out of the
handler, per `backend.jobs.worker.run_claimed_job`) when *nothing* in the
batch succeeded; otherwise it ends `done`, with `jobs.error` carrying a
summary of whatever went wrong (consistent with 最小單位可重試 — the user
just requests more of that type instead of retrying the whole job).
"""

import logging

from pydantic import BaseModel

from backend.core.config import get_settings
from backend.jobs.context import JobContext
from backend.jobs.registry import register_handler
from backend.llm.client import LLMClient, get_llm_client
from backend.models.question import Question
from backend.questions.prompts import build_prompt
from backend.questions.schemas import dump_payload, payload_model_for_type
from backend.questions.selection import GenerationUnit, select_units

logger = logging.getLogger(__name__)


def _require_str(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"job payload missing non-empty string {key!r}: {payload!r}")
    return value


def _require_int(payload: dict[str, object], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"job payload missing integer {key!r}: {payload!r}")
    return value


def _optional_int_list(payload: dict[str, object], key: str) -> list[int] | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, list):
        raise ValueError(f"job payload field {key!r} must be a list of integers: {payload!r}")
    result: list[int] = []
    for item in value:
        if not isinstance(item, int) or isinstance(item, bool):
            raise ValueError(f"job payload field {key!r} must be a list of integers: {payload!r}")
        result.append(item)
    return result


def _optional_str(payload: dict[str, object], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"job payload field {key!r} must be a string: {payload!r}")
    return value


async def _generate_one(
    llm: LLMClient,
    model_cls: type[BaseModel],
    question_type: str,
    unit: GenerationUnit,
    difficulty: str | None,
) -> Question:
    prompt = build_prompt(question_type, unit.contents, difficulty)
    result = await llm.chat(
        messages=[{"role": "user", "content": prompt}],
        response_model=model_cls,
        purpose=f"generate_question_{question_type}",
    )
    return Question(
        type=question_type,
        difficulty=difficulty,
        status="draft",
        payload=dump_payload(result),
        source_chunk_ids=unit.chunk_ids,
    )


@register_handler("generate_questions")
async def generate_questions(ctx: JobContext) -> None:
    settings = get_settings()
    llm = get_llm_client()
    session = ctx.session
    payload = ctx.payload

    question_type = _require_str(payload, "question_type")
    count = _require_int(payload, "count")
    if count <= 0:
        raise ValueError(f"count must be a positive integer, got {count}")
    document_ids = _optional_int_list(payload, "document_ids")
    category_ids = _optional_int_list(payload, "category_ids")
    difficulty = _optional_str(payload, "difficulty")

    # Validates question_type up front: an unknown type is a malformed
    # request, not a per-question failure, so it fails the whole job
    # immediately rather than being retried question-by-question.
    model_cls = payload_model_for_type(question_type)

    units = await select_units(
        session,
        question_type=question_type,
        document_ids=document_ids,
        category_ids=category_ids,
        count=count,
        settings=settings,
    )
    if not units:
        raise ValueError(
            f"no eligible source material for type={question_type!r} "
            f"scope document_ids={document_ids} category_ids={category_ids}"
        )

    total = len(units)
    success = 0
    failures: list[str] = []
    for index, unit in enumerate(units, start=1):
        try:
            question = await _generate_one(llm, model_cls, question_type, unit, difficulty)
            session.add(question)
            await session.commit()
            success += 1
        except Exception as exc:
            await session.rollback()
            logger.exception(
                "question %d/%d (type=%s, source chunks=%s) failed to generate",
                index,
                total,
                question_type,
                unit.chunk_ids,
            )
            failures.append(
                f"unit {index} (chunks={unit.chunk_ids}): {type(exc).__name__}: {exc}"
            )
        await ctx.set_progress(f"{index}/{total}")

    notes: list[str] = []
    if total < count:
        notes.append(
            f"requested {count} but only {total} eligible unit(s) of source material found"
        )
    if failures:
        notes.append(
            f"{len(failures)}/{total} generation call(s) failed:\n" + "\n".join(failures)
        )

    if success == 0:
        raise RuntimeError("; ".join(notes) or "all generation attempts failed")

    if notes:
        ctx.job.error = "; ".join(notes)
