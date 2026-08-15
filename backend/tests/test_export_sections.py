"""`backend.export.sections` — section grouping, per-section renumbering,
heading text and total-score computation (docs/export.md 題目依題型分節...固
定順序，節內連續編號；設定配分的節標題印「每題 X 分」；有配分時印總分).

Pure logic, no `python-docx`/database involved — the docx-level integration
(headers actually landing on the page, per-section numbers actually reset in
the rendered file) is covered in `test_export_job.py`.
"""

from backend.export.sections import build_sections, total_score
from backend.questions.schemas import (
    AnalogyQuestion,
    FillBlankQuestion,
    SingleChoiceQuestion,
    TrueFalseQuestion,
)

SC_A = SingleChoiceQuestion(stem="題A", options=["a", "b"], answer_index=0)
SC_B = SingleChoiceQuestion(stem="題B", options=["a", "b"], answer_index=1)
TF_A = TrueFalseQuestion(stem="是非題A", answer=True)
FB_A = FillBlankQuestion(stem="填充題 ____", answers=["x"])
AN_A = AnalogyQuestion(a="a", b="b", c="c", answer="d")


def test_sections_follow_fixed_order_regardless_of_input_order() -> None:
    sections = build_sections([AN_A, TF_A, SC_A], points=None)

    assert [section.question_type for section in sections] == [
        "single_choice",
        "true_false",
        "analogy",
    ]


def test_empty_sections_are_skipped_and_remaining_ones_renumbered_consecutively() -> None:
    sections = build_sections([AN_A, SC_A], points=None)

    # single_choice (present) is section 一, true_false/fill_blank/
    # short_answer/comparison (absent) contribute nothing, analogy (present)
    # becomes 二 -- not 六, its position in the fixed type order.
    assert [section.heading for section in sections] == ["一、選擇題", "二、類比題"]


def test_numbering_restarts_at_one_within_each_section() -> None:
    sections = build_sections([SC_A, SC_B, TF_A], points=None)

    single_choice_section = sections[0]
    true_false_section = sections[1]
    assert [number for number, _ in single_choice_section.numbered_questions] == [1, 2]
    assert [number for number, _ in true_false_section.numbered_questions] == [1]


def test_heading_shows_points_only_when_that_type_has_points() -> None:
    sections = build_sections([SC_A, TF_A], points={"single_choice": 5})

    by_type = {section.question_type: section for section in sections}
    assert by_type["single_choice"].heading == "一、選擇題（每題 5 分）"
    assert by_type["true_false"].heading == "二、是非題"


def test_points_blank_kept_only_for_single_choice_and_true_false_without_points() -> None:
    sections = build_sections([SC_A, TF_A, FB_A], points={"single_choice": 5})

    by_type = {section.question_type: section for section in sections}
    assert by_type["single_choice"].show_points_blank is False  # has points -> heading says it
    assert by_type["true_false"].show_points_blank is True  # no points -> keep the old blank
    assert by_type["fill_blank"].show_points_blank is False  # never had one to begin with


def test_total_score_is_none_when_no_points_given() -> None:
    assert total_score([SC_A, TF_A], points=None) is None
    assert total_score([SC_A, TF_A], points={}) is None


def test_total_score_sums_only_scored_types() -> None:
    # 2 single_choice * 5 + 1 true_false (no points assigned -> contributes 0)
    assert total_score([SC_A, SC_B, TF_A], points={"single_choice": 5}) == 10
