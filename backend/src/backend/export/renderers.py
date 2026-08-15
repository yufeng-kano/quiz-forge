"""One render function per question type (docs/export.md 每個題型一個 render
函式，輸入為該題型的 Pydantic model).

Each function's input is that type's model straight from
`backend.questions.schemas` — the same single definition used for LLM
structured output and API validation, never a parallel export-only type.
`mode="questions"` renders the printable stem only; `mode="answers"` renders
the same stem plus the answer/explanation, so the two papers never drift
apart on how a stem is built (this matters most for `analogy`, whose stem is
composed from slots, not stored verbatim).

`render_question` dispatches by `isinstance` on the already-validated
`QuestionModel` union (not a `dict[str, Callable]` keyed by the `type`
string) so the type checker narrows each branch to its concrete model and
catches a mismatched render call at check time, not at render time.
"""

from typing import Literal

from docx.document import Document

from backend.export import style
from backend.questions.schemas import (
    AnalogyQuestion,
    ComparisonQuestion,
    FillBlankQuestion,
    QuestionModel,
    ShortAnswerQuestion,
    SingleChoiceQuestion,
    TrueFalseQuestion,
)

ExportMode = Literal["questions", "answers"]

_OPTION_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _lettered_options(options: list[str]) -> list[str]:
    # `_OPTION_LETTERS` is a fixed 26-letter alphabet, always at least as
    # long as any real option list -- `strict=False` (explicit, not the
    # default) because that length difference is expected, not a bug to
    # catch: zip stops at `options`, the shorter of the two.
    return [
        f"({letter}) {option}" for letter, option in zip(_OPTION_LETTERS, options, strict=False)
    ]


def render_comparison(
    document: Document, number: int, question: ComparisonQuestion, mode: ExportMode
) -> None:
    """比較題 — 答案卷 render 成異同表（面向 x A x B），見 docs/question-bank.md。"""
    style.add_numbered_stem(document, number, question.stem)
    if mode == "answers":
        headers = ["面向", question.subject_a, question.subject_b]
        rows = [
            [difference.aspect, difference.a, difference.b]
            for difference in question.model_answer.differences
        ]
        style.add_answer_table(document, headers, rows)
        if question.model_answer.similarities:
            style.add_body_paragraph(
                document, "相同點：" + "、".join(question.model_answer.similarities)
            )


def render_analogy(
    document: Document, number: int, question: AnalogyQuestion, mode: ExportMode
) -> None:
    """類比題 — 題幹由 a/b/c 槽位組成「A 之於 B，猶如 C 之於＿＿」，恆一致；
    `options` 有值 render 成單選，`None` 則維持題幹本身的填空形式。"""
    stem_text = f"{question.a} 之於 {question.b}，猶如 {question.c} 之於＿＿"
    style.add_numbered_stem(document, number, stem_text)
    if question.options is not None:
        for line in _lettered_options(question.options):
            style.add_body_paragraph(document, line, indent=True)
    if mode == "answers":
        style.add_body_paragraph(document, f"答案：{question.answer}")
        if question.explanation:
            style.add_body_paragraph(document, f"解析：{question.explanation}")


def render_single_choice(
    document: Document,
    number: int,
    question: SingleChoiceQuestion,
    mode: ExportMode,
    *,
    show_points_blank: bool = True,
) -> None:
    style.add_numbered_stem(document, number, question.stem, points_field=show_points_blank)
    for line in _lettered_options(question.options):
        style.add_body_paragraph(document, line, indent=True)
    if mode == "answers":
        answer_letter = _OPTION_LETTERS[question.answer_index]
        answer_text = question.options[question.answer_index]
        style.add_body_paragraph(document, f"答案：({answer_letter}) {answer_text}")
        if question.explanation:
            style.add_body_paragraph(document, f"解析：{question.explanation}")


def render_true_false(
    document: Document,
    number: int,
    question: TrueFalseQuestion,
    mode: ExportMode,
    *,
    show_points_blank: bool = True,
) -> None:
    style.add_numbered_stem(document, number, question.stem, points_field=show_points_blank)
    if mode == "answers":
        answer_text = "○（正確）" if question.answer else "×（錯誤）"
        style.add_body_paragraph(document, f"答案：{answer_text}")
        if question.explanation:
            style.add_body_paragraph(document, f"解析：{question.explanation}")


def render_fill_blank(
    document: Document, number: int, question: FillBlankQuestion, mode: ExportMode
) -> None:
    """填充題 — `stem` 內的 `____` 標記在題目卷／答案卷都原樣保留，答案只在
    答案卷內依空格順序另列。"""
    style.add_numbered_stem(document, number, question.stem)
    if mode == "answers":
        answer_text = "、".join(
            f"{index}. {answer}" for index, answer in enumerate(question.answers, start=1)
        )
        style.add_body_paragraph(document, f"答案：{answer_text}")


def render_short_answer(
    document: Document, number: int, question: ShortAnswerQuestion, mode: ExportMode
) -> None:
    style.add_numbered_stem(document, number, question.stem)
    if mode == "answers":
        style.add_body_paragraph(document, f"參考答案：{question.model_answer}")
        for point in question.key_points:
            style.add_body_paragraph(document, f"• {point}", indent=True)


def render_question(
    document: Document,
    number: int,
    question: QuestionModel,
    mode: ExportMode,
    *,
    show_points_blank: bool = True,
) -> None:
    """Dispatch to the render function matching `question`'s concrete type.

    `show_points_blank` only ever reaches `single_choice`/`true_false` — the
    only two types the old per-question 配分 blank ever applied to
    (docs/export.md); the other four types' renderers don't take it at all.
    """
    if isinstance(question, ComparisonQuestion):
        render_comparison(document, number, question, mode)
    elif isinstance(question, AnalogyQuestion):
        render_analogy(document, number, question, mode)
    elif isinstance(question, SingleChoiceQuestion):
        render_single_choice(document, number, question, mode, show_points_blank=show_points_blank)
    elif isinstance(question, TrueFalseQuestion):
        render_true_false(document, number, question, mode, show_points_blank=show_points_blank)
    elif isinstance(question, FillBlankQuestion):
        render_fill_blank(document, number, question, mode)
    elif isinstance(question, ShortAnswerQuestion):
        render_short_answer(document, number, question, mode)
    else:
        raise ValueError(f"no renderer for question type {question.type!r}")
