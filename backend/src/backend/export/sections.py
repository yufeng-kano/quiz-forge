"""Fixed exam-paper section layout (docs/export.md 題目依題型分節...固定順序，
節內連續編號；配分印法：節內每題分數一致時節標題印「每題 X 分」；不一致時各
題題號後印「（X 分）」).

The section order and Chinese-numeral headings are a business rule fixed by
docs/export.md, not an environment tunable — so, per .rule 開發規則 (禁止硬
編碼...這些值必須放在...正式的常數設定模組中), they live here as one
constants module instead of being scattered as string literals across
`export/builder.py` / `export/job.py`.
"""

from collections.abc import Mapping, Sequence
from typing import Final, NamedTuple

from backend.questions.schemas import QuestionModel

# docs/export.md — 一、選擇題 二、是非題 三、填充題 四、問答題 五、比較題
# 六、類比題; empty sections are skipped and the remaining ones renumbered
# consecutively (see `build_sections`), but the *relative* order among the
# types that are present never changes.
SECTION_TYPE_ORDER: Final[list[str]] = [
    "single_choice",
    "true_false",
    "fill_blank",
    "short_answer",
    "comparison",
    "analogy",
]

SECTION_TITLES: Final[dict[str, str]] = {
    "single_choice": "選擇題",
    "true_false": "是非題",
    "fill_blank": "填充題",
    "short_answer": "問答題",
    "comparison": "比較題",
    "analogy": "類比題",
}

CHINESE_ORDINALS: Final[list[str]] = ["一", "二", "三", "四", "五", "六"]

# Only `single_choice`/`true_false` ever had the old per-question 配分 blank
# (docs/export.md 有配分的題目不再印「配分：___分」手填欄；完全沒設配分維持
# 現行手填欄行為) — the other four types never had one and don't gain one now.
_POINTS_BLANK_ELIGIBLE_TYPES: Final[frozenset[str]] = frozenset({"single_choice", "true_false"})


class IdentifiedQuestion(NamedTuple):
    """One selected question paired with its database id — the id only ever
    matters for looking up a per-question 配分 override (`question_points`
    in docs/export.md); nothing downstream renders it."""

    question_id: int
    question: QuestionModel


def resolve_points(
    questions: Sequence[IdentifiedQuestion],
    points: Mapping[str, int] | None,
    question_points: Mapping[int, int] | None,
) -> dict[int, int]:
    """`{question_id: resolved points}` for every question that has *any*
    points assigned — a per-question override (`question_points`) takes
    precedence over its type's default (`points`, docs/export.md 逐題覆
    寫...優先於題型預設); a question with neither is simply absent from the
    result, so `sum(resolve_points(...).values())` already equals the whole
    exam's total (types/questions with no points contribute 0)."""
    resolved: dict[int, int] = {}
    for question_id, question in questions:
        override = question_points.get(question_id) if question_points is not None else None
        if override is not None:
            resolved[question_id] = override
            continue
        type_default = points.get(question.type) if points is not None else None
        if type_default is not None:
            resolved[question_id] = type_default
    return resolved


class SectionQuestion(NamedTuple):
    """One question already renumbered within its section, plus how it
    should print its resolved 配分: `points_suffix` is the value to print as
    「（X 分）」 right after the question number (only set in a *mixed*
    section — a uniform section states its points once, in the heading, via
    `Section.heading`), and `show_points_blank` is whether the old
    「配分：___分」 hand-fill blank should still appear."""

    number: int
    question_id: int
    question: QuestionModel
    points_suffix: int | None
    show_points_blank: bool


class Section(NamedTuple):
    """One 分節: a fixed-order type, its heading text (carrying a uniform
    「每題 X 分」 when every question in it resolves to the same nonzero
    points), and its questions renumbered 1..N within just this section."""

    question_type: str
    heading: str
    questions: list[SectionQuestion]


def build_sections(
    questions: Sequence[IdentifiedQuestion],
    resolved_points: Mapping[int, int],
) -> list[Section]:
    """Group `questions` into `SECTION_TYPE_ORDER` order, dropping empty
    sections and renumbering the Chinese ordinal + in-section question
    numbers consecutively over what's left. Relative order of same-type
    questions is preserved from the caller's input order.

    `resolved_points` (from `resolve_points`) decides, per section, whether
    every question resolves to the same nonzero points (heading gets 「每題
    X 分」, no question needs a suffix) or not (each question with points
    gets its own 「（X 分）」 suffix instead)."""
    buckets: dict[str, list[IdentifiedQuestion]] = {t: [] for t in SECTION_TYPE_ORDER}
    for item in questions:
        buckets[item.question.type].append(item)

    sections: list[Section] = []
    for question_type in SECTION_TYPE_ORDER:
        group = buckets[question_type]
        if not group:
            continue
        ordinal = CHINESE_ORDINALS[len(sections)]
        heading = f"{ordinal}、{SECTION_TITLES[question_type]}"

        values = [resolved_points.get(item.question_id) for item in group]
        uniform_value = values[0]
        is_uniform = uniform_value is not None and all(value == uniform_value for value in values)
        if is_uniform:
            heading = f"{heading}（每題 {uniform_value} 分）"

        section_questions: list[SectionQuestion] = []
        for number, item in enumerate(group, start=1):
            question_points = resolved_points.get(item.question_id)
            points_suffix = None if is_uniform else question_points
            show_points_blank = (
                question_type in _POINTS_BLANK_ELIGIBLE_TYPES and question_points is None
            )
            section_questions.append(
                SectionQuestion(
                    number=number,
                    question_id=item.question_id,
                    question=item.question,
                    points_suffix=points_suffix,
                    show_points_blank=show_points_blank,
                )
            )
        sections.append(
            Section(question_type=question_type, heading=heading, questions=section_questions)
        )
    return sections


def total_score(resolved_points: Mapping[int, int]) -> int | None:
    """`None` when no question resolved to any points at all (docs/export.md
    有配分時印總分 -- nothing to print otherwise); else the sum of every
    resolved per-question value (unassigned questions already don't appear
    in `resolved_points`, so they contribute 0 by omission)."""
    if not resolved_points:
        return None
    return sum(resolved_points.values())
