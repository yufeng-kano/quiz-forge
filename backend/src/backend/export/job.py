"""`export_docx` job handler (docs/export.md 選題流程 step 2-3).

Validates every requested question id exists *and* is `approved` — 只有
`approved` 題目出現在...Word 匯出的選題範圍 (docs/question-bank.md 審題流程) —
before rendering anything; an offending id fails the whole job (this is a
request-shape problem, not a per-question one, so unlike `generate_questions`
it is never "partially" run). Rendering itself (`python-docx`, sync/CPU-bound)
runs in `asyncio.to_thread` one question at a time so `jobs.progress` reflects
real per-question progress, matching .rule 使用者體驗規則 (逐頁/逐題進度)。

Rendering order is section-grouped (docs/export.md 題目依題型分節...固定順序，
節內連續編號), computed once via `backend.export.sections.build_sections` —
this handler never re-derives that grouping/heading logic itself, it only
drives `ExamPaperBuilder` through what that module already worked out.
"""

import asyncio

from sqlalchemy import select

from backend.core.config import get_settings
from backend.export.builder import ExamPaperBuilder
from backend.export.paper import SUPPORTED_PAPER_SIZES
from backend.export.paths import answers_docx_path, questions_docx_path
from backend.export.sections import build_sections, total_score
from backend.jobs.context import JobContext
from backend.jobs.registry import register_handler
from backend.models.export import Export
from backend.models.question import Question
from backend.questions.schemas import QUESTION_TYPE_MODELS, parse_question


def _require_paper_size(payload: dict[str, object]) -> str:
    value = payload.get("paper_size")
    if not isinstance(value, str) or value not in SUPPORTED_PAPER_SIZES:
        raise ValueError(
            f"job payload paper_size must be one of {sorted(SUPPORTED_PAPER_SIZES)}, got {value!r}"
        )
    return value


def _require_title(payload: dict[str, object]) -> str:
    value = payload.get("title")
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"job payload missing non-empty string title: {payload!r}")
    return value


def _parse_points(payload: dict[str, object]) -> dict[str, int] | None:
    """`payload["points"]` (optional 每題型配分, docs/export.md) validated
    into `{question_type: positive_int}`, or `None` when omitted."""
    value = payload.get("points")
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError(f"job payload field points must be an object: {payload!r}")
    points: dict[str, int] = {}
    for question_type, raw_amount in value.items():
        if question_type not in QUESTION_TYPE_MODELS:
            raise ValueError(f"points key {question_type!r} is not a known question type")
        if not isinstance(raw_amount, int) or isinstance(raw_amount, bool) or raw_amount <= 0:
            raise ValueError(
                f"points value for {question_type!r} must be a positive integer, got {raw_amount!r}"
            )
        points[question_type] = raw_amount
    return points


def _require_question_ids(payload: dict[str, object]) -> list[int]:
    value = payload.get("question_ids")
    if not isinstance(value, list) or not value:
        raise ValueError(f"job payload missing non-empty list question_ids: {payload!r}")
    ids: list[int] = []
    for item in value:
        if not isinstance(item, int) or isinstance(item, bool):
            raise ValueError(
                f"job payload field question_ids must be a list of integers: {payload!r}"
            )
        ids.append(item)
    # De-duplicate while preserving the caller's order -- that order becomes
    # the paper's numbering order.
    seen: set[int] = set()
    ordered: list[int] = []
    for question_id in ids:
        if question_id not in seen:
            seen.add(question_id)
            ordered.append(question_id)
    return ordered


@register_handler("export_docx")
async def export_docx(ctx: JobContext) -> None:
    settings = get_settings()
    session = ctx.session
    payload = ctx.payload

    paper_size = _require_paper_size(payload)
    title = _require_title(payload)
    points = _parse_points(payload)
    question_ids = _require_question_ids(payload)

    rows = (
        (await session.execute(select(Question).where(Question.id.in_(question_ids))))
        .scalars()
        .all()
    )
    by_id = {question.id: question for question in rows}

    missing_ids = [qid for qid in question_ids if qid not in by_id]
    not_approved_ids = [
        qid for qid in question_ids if qid in by_id and by_id[qid].status != "approved"
    ]
    if missing_ids or not_approved_ids:
        problems: list[str] = []
        if missing_ids:
            problems.append(f"question ids not found: {missing_ids}")
        if not_approved_ids:
            problems.append(f"question ids not approved: {not_approved_ids}")
        raise ValueError("; ".join(problems))

    questions = [by_id[qid] for qid in question_ids]
    models = [parse_question(question.type, question.payload) for question in questions]

    export = Export(title=title, paper_size=paper_size, question_ids=question_ids)
    session.add(export)
    await session.commit()
    await session.refresh(export)

    total = len(questions)
    await ctx.set_progress(f"0/{total}")

    builder = await asyncio.to_thread(ExamPaperBuilder, paper_size, title)
    total_points = total_score(models, points)
    if total_points is not None:
        await asyncio.to_thread(builder.add_total_score, total_points)

    rendered = 0
    for section in build_sections(models, points):
        await asyncio.to_thread(builder.add_section_heading, section.heading)
        for number, model in section.numbered_questions:
            await asyncio.to_thread(
                builder.render_question,
                number,
                model,
                show_points_blank=section.show_points_blank,
            )
            rendered += 1
            await ctx.set_progress(f"{rendered}/{total}")

    data_dir = settings.data_dir
    questions_path = questions_docx_path(data_dir, export.id)
    answers_path = answers_docx_path(data_dir, export.id)
    await asyncio.to_thread(builder.save, questions_path, answers_path)

    export.docx_path = str(questions_path)
    export.answer_docx_path = str(answers_path)
    await session.commit()
