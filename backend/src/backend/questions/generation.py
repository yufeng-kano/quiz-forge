"""`generate_questions` job handler (docs/question-bank.md 出題流程).

Wires `backend.questions.selection` (which chunk(s) feed each question) to
`backend.questions.prompts` (what to ask) and `backend.llm.client.LLMClient`
(the actual `TEXT_MODEL` call, `response_format: json_schema` of the
specific type's Pydantic model). Every generated question is stored
`status="draft"` immediately.

One job payload carries `items: [{question_type, count, difficulty?}, ...]` —
one or more「題型 × 數量 × 難度」combos generated together
(docs/question-bank.md 出題流程 step 1). Difficulty is per item (D31); a
job-level `difficulty` key is honoured as fallback for jobs queued before.
Material selection and generation for each item reuses the exact same
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
regeneration call with a corrective instruction appended; a hit on the retry
too raises `SourceReferentialPhraseError`, which falls into the same
per-question failure path as any other generation error above — the question
is not inserted, the job keeps going, and `jobs.error` records the
teacher-facing reason class「題幹引用教材」(not the exception name or the
banned phrase). This is pure string/regex matching, no extra LLM judge call,
and both the first and the retry `llm.chat()` calls record `llm_usage` as
normal (that recording lives inside `LLMClient`, so it needs no
special-casing here).

The corrective instruction deliberately does NOT quote the offending phrase
back at the model, and explicitly frames the self-containment rules as
meta-instructions rather than subject matter. A live run showed both matter:
quoting 「根據教材」 back at the model seeded a meta-question ABOUT the rule
itself (a stem asking which option best follows「題幹自足原則」, with an
option quoting the very banned phrase) — the string check correctly caught
it, but only after a wasted regeneration. `_corrective_instruction` instead
names the violation category, asks for a brand-new question on the same
source-material subject, and tells the model not to mention, quote, or test
the writing rules themselves.
"""

import logging
import re
from collections.abc import Iterator

from pydantic import BaseModel

from backend.core.config import get_settings
from backend.jobs.context import JobContext
from backend.jobs.error_summary import (
    GENERATION_SOURCE_REFERENTIAL,
    JOB_FAILED,
    JobFailed,
    generation_no_material,
    generation_short_material,
    generation_unknown_type,
    join_summaries,
    summarize_generation_failures,
)
from backend.jobs.registry import register_handler
from backend.llm.client import LLMClient, get_llm_client
from backend.models.question import Question
from backend.questions.embedding import EMBED_QUESTION_PURPOSE, flatten_question_payload
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
    in the job's failure summary as the reason class「題幹引用教材」."""


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


def _corrective_instruction() -> str:
    """Appended to the original prompt on the one retry after a banned-phrase
    hit.

    Deliberately does NOT quote the offending phrase back at the model — a
    live run showed that echoing 「根據教材」 in the corrective text seeded a
    meta-question ABOUT the self-containment rule itself (stem asking which
    option best follows the rule, with an option quoting the banned phrase
    as an example of what NOT to do — still a hit, but on a question whose
    entire topic had drifted to "the writing rules" instead of the source
    material). Describing the violation category instead, and explicitly
    telling the model these are meta-instructions to itself rather than
    subject matter to test, avoids both problems at once.
    """
    return (
        "\n\n上一次的輸出不合格：它提到了教材、課文、上文或本文本身（指涉來源文件的"
        "措辭），而不是只講教材要教的知識內容，這樣的題目不能用。\n"
        "請針對同一個知識主題重新出一題全新的題目（stem、選項、答案、解說都要重寫），"
        "內容仍然是這份教材在教的知識本身，考的知識範圍不要換掉。\n"
        "重要：你剛剛看到的這些出題規則，是我對出題者下的寫作指示，不是教材要考的知識"
        "本身——新題目不能拿這些規則當題目內容、不能問「怎樣才符合這些規則」，也不能"
        "在題幹、選項或解說裡引用或重複上一版用過的錯誤措辭。"
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
    """Generates and embeds one question. The embedding call is inside this
    function's own try/except-free body, so its failure surfaces to
    `generate_questions`'s per-unit `try/except` exactly like a generation or
    self-containment failure would — the question is not inserted, the job's
    other questions are unaffected, and it shows up in `jobs.error`
    (docs/question-bank.md 題目向量化與語意搜尋 — generate_questions job 入庫時
    同步 embed，本來就在背景執行)."""
    prompt = build_prompt(question_type, unit.contents, difficulty)
    payload, banned_phrase = await _generate_payload(llm, model_cls, question_type, prompt)
    if banned_phrase is not None:
        retry_prompt = prompt + _corrective_instruction()
        payload, banned_phrase = await _generate_payload(
            llm, model_cls, question_type, retry_prompt
        )
        if banned_phrase is not None:
            raise SourceReferentialPhraseError(
                f"generated {question_type!r} question still contains source-referential "
                f"phrase {banned_phrase!r} after regeneration: {payload!r}"
            )
    [embedding] = await llm.embed(
        texts=[flatten_question_payload(question_type, payload)],
        purpose=EMBED_QUESTION_PURPOSE,
    )
    return Question(
        type=question_type,
        difficulty=difficulty,
        status="draft",
        payload=payload,
        source_chunk_ids=unit.chunk_ids,
        embedding=embedding,
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
    # Jobs queued before D31 carried one shared difficulty at the job level;
    # an item without its own difficulty falls back to it so an old job's
    # retry behaves as originally requested
    # (docs/decisions/2026-08-18-generate-row-difficulty-percent-scoring.md).
    fallback_difficulty = _optional_str(payload, "difficulty")

    # Pass 1: resolve every item's source material up front, so the progress
    # denominator (total_all_items) is known before any generation call
    # starts. An item naming an unknown type or whose scope has no eligible
    # material contributes zero units and a note — exactly like a
    # single-type job's "no eligible material" case used to fail that job,
    # except here it only knocks out *this* item, not the rest of `items`.
    item_plans: list[tuple[str, type[BaseModel], list[GenerationUnit], str | None]] = []
    notes: list[str] = []
    for item_index, item_payload in enumerate(items_payload, start=1):
        question_type = _require_str(item_payload, "question_type")
        count = _require_int(item_payload, "count")
        item_difficulty = _optional_str(item_payload, "difficulty") or fallback_difficulty
        if count <= 0:
            raise ValueError(
                f"item {item_index} count must be a positive integer, got {count}"
            )

        try:
            model_cls = payload_model_for_type(question_type)
        except ValueError:
            notes.append(generation_unknown_type())
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
            notes.append(generation_no_material(question_type))
            continue
        if len(units) < count:
            notes.append(generation_short_material(count, len(units)))
        item_plans.append((question_type, model_cls, units, item_difficulty))

    total = sum(len(units) for _, _, units, _ in item_plans)

    # Pass 2: generate every unit of every surviving item, in order, sharing
    # one running index/total across the whole job (docs/question-bank.md —
    # progress 以全部題數合計顯示).
    success = 0
    failure_reasons: list[str | None] = []
    index = 0
    for question_type, model_cls, units, item_difficulty in item_plans:
        for unit in units:
            index += 1
            try:
                question = await _generate_one(
                    llm, model_cls, question_type, unit, item_difficulty
                )
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
                if isinstance(exc, SourceReferentialPhraseError):
                    failure_reasons.append(GENERATION_SOURCE_REFERENTIAL)
                else:
                    failure_reasons.append(None)
            await ctx.set_progress(f"{index}/{total}")

    if failure_reasons:
        notes.append(summarize_generation_failures(failure_reasons))

    if success == 0:
        raise JobFailed(join_summaries(notes) or JOB_FAILED)

    if notes:
        ctx.job.error = join_summaries(notes)
