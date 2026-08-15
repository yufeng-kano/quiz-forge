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

題幹自足檢查（docs/question-bank.md 題幹自足原則）: every generated payload is
scanned for source-referential wording (「根據教材內容」「文中提到」等，see
`_SOURCE_REFERENTIAL_PATTERNS`) after parsing. A hit triggers exactly one
regeneration call with a corrective instruction appended naming the offending
phrase; a hit on the retry too raises `SourceReferentialPhraseError`, which
falls into the same per-question failure path as any other generation error
above — the question is not inserted, the job keeps going, and the phrase
shows up in `jobs.error`. This is pure string/regex matching, no extra LLM
judge call, and both the first and the retry `llm.chat()` calls record
`llm_usage` as normal (that recording lives inside `LLMClient`, so it needs
no special-casing here).
"""

import logging
import re
from collections.abc import Iterator

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


class SourceReferentialPhraseError(RuntimeError):
    """A generated question still names the source document (docs/question-bank.md
    題幹自足原則) after one regeneration attempt. Raised from `_generate_one` and
    caught by `generate_questions`'s existing per-question failure handling —
    same treatment as a schema-validation failure: the question is not
    inserted, the job's other questions are unaffected, and it is recorded
    in the job's failure summary."""


# docs/question-bank.md 題幹自足原則 — wording that leaks "you had to have read
# the source document" into a question. Curated to avoid false positives on
# legitimate quiz text: bare 根據 (e.g. 「根據牛頓第二定律」) and bare 內容
# (e.g. 「下列內容何者正確」) must NOT match on their own — only 根據/依據
# immediately followed by a source-word, or a source-word compounded with
# 指出/提到/中/所述, counts.
_SOURCE_REFERENTIAL_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"(根據|依據)(教材|課文|本文|上文|內文|內容)"),
    re.compile(r"教材(內容|指出|提到|中)"),
    re.compile(r"課文(指出|提到|中)"),
    re.compile(r"(本|上|全|內)文(提到|指出|中|所述)"),
    re.compile(r"文中"),
    re.compile(r"如(前|上)所述"),
]


def _iter_strings(value: object) -> Iterator[str]:
    """Walk a parsed question payload's dict/list/str tree generically, so
    every user-visible text field (stem, options, answers, model_answer,
    key_points, explanation, comparison's nested differences, ...) is
    covered without a per-type field list — a new question type's fields
    are covered for free."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _iter_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_strings(item)


def _find_banned_phrase(payload: dict[str, object]) -> str | None:
    """The first source-referential phrase found anywhere in `payload`'s
    text, or `None` if it is clean."""
    for text in _iter_strings(payload):
        for pattern in _SOURCE_REFERENTIAL_PATTERNS:
            match = pattern.search(text)
            if match:
                return match.group(0)
    return None


def _corrective_instruction(banned_phrase: str) -> str:
    return (
        f"\n\n上一版題目使用了指涉來源文件的措辭「{banned_phrase}」，這違反題幹自足原則。"
        "請重新出題：完全避免「根據教材／課文／本文／上文／文中」這類指涉來源文件的措辭，"
        "題幹、選項、答案與解說都要自帶足夠脈絡，讓沒看過原文的人也能理解並作答；若題目"
        "原本提到教材內部編號（如章節、Lab 編號、表格編號），請改成描述該事物本身的內容。"
    )


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


async def _generate_payload(
    llm: LLMClient, model_cls: type[BaseModel], question_type: str, prompt: str
) -> tuple[dict[str, object], str | None]:
    """One `llm.chat()` call, parsed to a jsonb-ready payload plus the first
    banned source-referential phrase found in it (`None` if clean)."""
    result = await llm.chat(
        messages=[{"role": "user", "content": prompt}],
        response_model=model_cls,
        purpose=f"generate_question_{question_type}",
    )
    payload = dump_payload(result)
    return payload, _find_banned_phrase(payload)


async def _generate_one(
    llm: LLMClient,
    model_cls: type[BaseModel],
    question_type: str,
    unit: GenerationUnit,
    difficulty: str | None,
) -> Question:
    prompt = build_prompt(question_type, unit.contents, difficulty)
    payload, banned_phrase = await _generate_payload(llm, model_cls, question_type, prompt)
    if banned_phrase is not None:
        retry_prompt = prompt + _corrective_instruction(banned_phrase)
        payload, banned_phrase = await _generate_payload(
            llm, model_cls, question_type, retry_prompt
        )
        if banned_phrase is not None:
            raise SourceReferentialPhraseError(
                f"generated {question_type!r} question still contains source-referential "
                f"phrase {banned_phrase!r} after regeneration: {payload!r}"
            )
    return Question(
        type=question_type,
        difficulty=difficulty,
        status="draft",
        payload=payload,
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
