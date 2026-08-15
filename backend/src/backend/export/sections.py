"""Fixed exam-paper section layout (docs/export.md 題目依題型分節...固定順序，
節內連續編號；設定配分的節標題印「每題 X 分」).

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
# (docs/export.md 舊制單題「配分：___分」欄位改成只在該題型沒有指定配分時才
# 保留) — the other four types never had one and don't gain one now.
_POINTS_BLANK_ELIGIBLE_TYPES: Final[frozenset[str]] = frozenset({"single_choice", "true_false"})


class Section(NamedTuple):
    """One 分節: a fixed-order type, its heading text, and its questions
    renumbered 1..N within just this section."""

    question_type: str
    heading: str
    show_points_blank: bool
    numbered_questions: list[tuple[int, QuestionModel]]


def build_sections(
    questions: Sequence[QuestionModel], points: Mapping[str, int] | None
) -> list[Section]:
    """Group `questions` into `SECTION_TYPE_ORDER` order, dropping empty
    sections and renumbering the Chinese ordinal + in-section question
    numbers consecutively over what's left. Relative order of same-type
    questions is preserved from the caller's input order."""
    buckets: dict[str, list[QuestionModel]] = {t: [] for t in SECTION_TYPE_ORDER}
    for question in questions:
        buckets[question.type].append(question)

    sections: list[Section] = []
    for question_type in SECTION_TYPE_ORDER:
        group = buckets[question_type]
        if not group:
            continue
        ordinal = CHINESE_ORDINALS[len(sections)]
        heading = f"{ordinal}、{SECTION_TITLES[question_type]}"
        assigned_points = points.get(question_type) if points is not None else None
        if assigned_points is not None:
            heading = f"{heading}（每題 {assigned_points} 分）"
        show_points_blank = (
            question_type in _POINTS_BLANK_ELIGIBLE_TYPES and assigned_points is None
        )
        sections.append(
            Section(
                question_type=question_type,
                heading=heading,
                show_points_blank=show_points_blank,
                numbered_questions=list(enumerate(group, start=1)),
            )
        )
    return sections


def total_score(questions: Sequence[QuestionModel], points: Mapping[str, int] | None) -> int | None:
    """`None` when no `points` were given at all (docs/export.md 有配分時印
    總分 -- nothing to print otherwise); else the sum of `points[type] *
    count(type)` over the selected questions (types with no assigned points
    contribute 0, since there is no per-question value to multiply)."""
    if not points:
        return None
    counts: dict[str, int] = {}
    for question in questions:
        counts[question.type] = counts.get(question.type, 0) + 1
    return sum(points.get(question_type, 0) * count for question_type, count in counts.items())
