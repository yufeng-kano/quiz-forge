"""`generate_questions` job handler (docs/question-bank.md 出題流程).

Wires `backend.questions.selection` (which chunk(s) feed each question) to
`backend.questions.prompts` (what to ask) and `backend.llm.client.LLMClient`
(the actual `TEXT_MODEL` call, `response_format: json_schema` of the
specific type's Pydantic model). Every generated question is stored
`status="draft"` immediately.

One job payload carries `items: [{question_type, count}, ...]` — one or more
「題型 × 數量」combos generated together (docs/question-bank.md 出題流程 step
1). Material selection and generation for each item reuses the exact same
per-type logic a single-type job always used; the only thing multi-item adds
is an outer loop over `items` and a progress denominator that spans all of
them (`n/total_all_items`, `total_all_items` = the sum of eligible units
actually found per item, mirroring how a single-type job's total was already
"eligible units found", not "units requested").

Failure handling (.rule 反偷懶規則 — 禁止吞例外／禁止部分處理；docs/question-bank.md —
生成一律逐題進行，單一項目全失敗不影響其他項目): both a whole item finding no
eligible material (or naming an unknown type) and a single question's
generation call failing are caught, logged in full, and recorded in the
job's final error summary — neither aborts the remaining items/questions.
The job only ends up `failed` (raises out of the handler, per
`backend.jobs.worker.run_claimed_job`) when *nothing* across *any* item
succeeded; otherwise it ends `done`, with `jobs.error` carrying a summary of
whatever went wrong (consistent with 最小單位可重試 — the user just requests
more of that type/item instead of retrying the whole job).
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


def _require_items(payload: dict[str, object]) -> list[dict[str, object]]:
    """`payload["items"]` as a non-empty list of `{question_type, count}`
    dicts. A malformed `items` (missing, empty, wrong shape) is a malformed
    request rather than a single item's generation failure, so it raises
    straight out of the handler like the other `_require_*`/`_optional_*`
    payload parsers — it fails the whole job immediately instead of being
    retried item-by-item."""
    value = payload.get("items")
    if not isinstance(value, list) or not value:
        raise ValueError(f"job payload missing non-empty list 'items': {payload!r}")
    items: list[dict[str, object]] = []
    for entry in value:
        if not isinstance(entry, dict):
            raise ValueError(f"job payload 'items' entries must be objects: {payload!r}")
        items.append(entry)
    return items


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

    items_payload = _require_items(payload)
    document_ids = _optional_int_list(payload, "document_ids")
    category_ids = _optional_int_list(payload, "category_ids")
    difficulty = _optional_str(payload, "difficulty")

    # Pass 1: resolve every item's source material up front, so the progress
    # denominator (total_all_items) is known before any generation call
    # starts. An item naming an unknown type or whose scope has no eligible
    # material contributes zero units and a note — exactly like a
    # single-type job's "no eligible material" case used to fail that job,
    # except here it only knocks out *this* item, not the rest of `items`.
    item_plans: list[tuple[str, type[BaseModel], list[GenerationUnit]]] = []
    notes: list[str] = []
    for item_index, item_payload in enumerate(items_payload, start=1):
        question_type = _require_str(item_payload, "question_type")
        count = _require_int(item_payload, "count")
        if count <= 0:
            raise ValueError(
                f"item {item_index} count must be a positive integer, got {count}"
            )

        try:
            model_cls = payload_model_for_type(question_type)
        except ValueError as exc:
            notes.append(f"item {item_index} (type={question_type!r}): {exc}")
            continue

        units = await select_units(
            session,
            question_type=question_type,
            document_ids=document_ids,
            category_ids=category_ids,
            count=count,
            settings=settings,
        )
        if not units:
            notes.append(
                f"item {item_index} (type={question_type!r}): no eligible source material "
                f"scope document_ids={document_ids} category_ids={category_ids}"
            )
            continue
        if len(units) < count:
            notes.append(
                f"item {item_index} (type={question_type!r}): requested {count} but only "
                f"{len(units)} eligible unit(s) of source material found"
            )
        item_plans.append((question_type, model_cls, units))

    total = sum(len(units) for _, _, units in item_plans)

    # Pass 2: generate every unit of every surviving item, in order, sharing
    # one running index/total across the whole job (docs/question-bank.md —
    # progress 以全部題數合計顯示).
    success = 0
    failures: list[str] = []
    index = 0
    for question_type, model_cls, units in item_plans:
        for unit in units:
            index += 1
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
                    f"unit {index} (type={question_type!r}, chunks={unit.chunk_ids}): "
                    f"{type(exc).__name__}: {exc}"
                )
            await ctx.set_progress(f"{index}/{total}")

    if failures:
        notes.append(
            f"{len(failures)}/{total} generation call(s) failed:\n" + "\n".join(failures)
        )

    if success == 0:
        raise RuntimeError("; ".join(notes) or "all generation attempts failed")

    if notes:
        ctx.job.error = "; ".join(notes)
