"""`backend.export.sections` — section grouping, per-section renumbering,
heading text, per-question 配分覆寫 resolution and total-score computation
(docs/export.md 題目依題型分節...固定順序，節內連續編號；配分印法：節內每題
分數一致時節標題印「每題 X 分」；不一致時各題題號後印「（X 分）」；有配分時
印總分).

Pure logic, no `python-docx`/database involved — the docx-level integration
(headers actually landing on the page, per-section numbers actually reset in
the rendered file) is covered in `test_export_job.py`.
"""

from backend.export.sections import IdentifiedQuestion, build_sections, resolve_points, total_score
from backend.questions.schemas import (
    AnalogyQuestion,
    FillBlankQuestion,
    QuestionModel,
    SingleChoiceQuestion,
    TrueFalseQuestion,
)

SC_A = SingleChoiceQuestion(stem="題A", options=["a", "b"], answer_index=0)
SC_B = SingleChoiceQuestion(stem="題B", options=["a", "b"], answer_index=1)
TF_A = TrueFalseQuestion(stem="是非題A", answer=True)
FB_A = FillBlankQuestion(stem="填充題 ____", answers=["x"])
AN_A = AnalogyQuestion(a="a", b="b", c="c", answer="d")


def _identified(*pairs: tuple[int, QuestionModel]) -> list[IdentifiedQuestion]:
    return [IdentifiedQuestion(question_id, question) for question_id, question in pairs]


# ---------------------------------------------------------------------------
# resolve_points — override precedence
# ---------------------------------------------------------------------------


def test_resolve_points_uses_type_default_when_no_override() -> None:
    questions = _identified((1, SC_A), (2, TF_A))

    resolved = resolve_points(questions, points={"single_choice": 5}, question_points=None)

    assert resolved == {1: 5}  # true_false has no type default -> absent


def test_resolve_points_override_takes_precedence_over_type_default() -> None:
    questions = _identified((1, SC_A))

    resolved = resolve_points(
        questions, points={"single_choice": 5}, question_points={1: 8}
    )

    assert resolved == {1: 8}


def test_resolve_points_override_applies_even_without_a_type_default() -> None:
    questions = _identified((1, SC_A), (2, TF_A))

    resolved = resolve_points(questions, points=None, question_points={2: 3})

    assert resolved == {2: 3}


def test_resolve_points_empty_when_nothing_assigned() -> None:
    questions = _identified((1, SC_A))

    assert resolve_points(questions, points=None, question_points=None) == {}


# ---------------------------------------------------------------------------
# build_sections — grouping / numbering / headings
# ---------------------------------------------------------------------------


def test_sections_follow_fixed_order_regardless_of_input_order() -> None:
    questions = _identified((1, AN_A), (2, TF_A), (3, SC_A))

    sections = build_sections(questions, resolved_points={})

    assert [section.question_type for section in sections] == [
        "single_choice",
        "true_false",
        "analogy",
    ]


def test_empty_sections_are_skipped_and_remaining_ones_renumbered_consecutively() -> None:
    questions = _identified((1, AN_A), (2, SC_A))

    sections = build_sections(questions, resolved_points={})

    # single_choice (present) is section 一, true_false/fill_blank/
    # short_answer/comparison (absent) contribute nothing, analogy (present)
    # becomes 二 -- not 六, its position in the fixed type order.
    assert [section.heading for section in sections] == ["一、選擇題", "二、類比題"]


def test_numbering_restarts_at_one_within_each_section() -> None:
    questions = _identified((1, SC_A), (2, SC_B), (3, TF_A))

    sections = build_sections(questions, resolved_points={})

    single_choice_section = sections[0]
    true_false_section = sections[1]
    assert [sq.number for sq in single_choice_section.questions] == [1, 2]
    assert [sq.number for sq in true_false_section.questions] == [1]


def test_heading_shows_uniform_points_only_when_every_question_in_section_matches() -> None:
    questions = _identified((1, SC_A), (2, SC_B), (3, TF_A))

    sections = build_sections(questions, resolved_points={1: 5, 2: 5})

    by_type = {section.question_type: section for section in sections}
    assert by_type["single_choice"].heading == "一、選擇題（每題 5 分）"
    assert by_type["true_false"].heading == "二、是非題"  # no points at all -> plain heading


def test_heading_falls_back_to_per_question_suffix_when_section_points_differ() -> None:
    questions = _identified((1, SC_A), (2, SC_B))

    sections = build_sections(questions, resolved_points={1: 5, 2: 8})

    section = sections[0]
    assert section.heading == "一、選擇題"  # not uniform -> no "每題 X 分"
    suffixes = {sq.question_id: sq.points_suffix for sq in section.questions}
    assert suffixes == {1: 5, 2: 8}


def test_heading_falls_back_to_suffix_when_only_some_questions_in_section_have_points() -> None:
    questions = _identified((1, SC_A), (2, SC_B))

    sections = build_sections(questions, resolved_points={1: 5})  # 2 has none

    section = sections[0]
    assert section.heading == "一、選擇題"
    suffixes = {sq.question_id: sq.points_suffix for sq in section.questions}
    assert suffixes == {1: 5, 2: None}  # only the scored question gets a suffix


def test_uniform_section_questions_carry_no_suffix() -> None:
    questions = _identified((1, SC_A), (2, SC_B))

    sections = build_sections(questions, resolved_points={1: 5, 2: 5})

    section = sections[0]
    assert all(sq.points_suffix is None for sq in section.questions)


def test_points_blank_kept_only_for_single_choice_and_true_false_without_resolved_points() -> None:
    questions = _identified((1, SC_A), (2, TF_A), (3, FB_A))

    sections = build_sections(questions, resolved_points={1: 5})

    by_type = {section.question_type: section for section in sections}
    single_choice_q = by_type["single_choice"].questions[0]
    true_false_q = by_type["true_false"].questions[0]
    fill_blank_q = by_type["fill_blank"].questions[0]
    assert single_choice_q.show_points_blank is False  # has resolved points
    assert true_false_q.show_points_blank is True  # no points -> keep the old blank
    assert fill_blank_q.show_points_blank is False  # never had one to begin with


def test_points_blank_dropped_even_for_a_suffixed_question_in_a_mixed_section() -> None:
    """A question that resolved to points never keeps the hand-fill blank,
    regardless of whether its section ended up uniform (heading-only) or
    mixed (per-question suffix)."""
    questions = _identified((1, SC_A), (2, SC_B))

    sections = build_sections(questions, resolved_points={1: 5, 2: 8})

    section = sections[0]
    assert all(sq.show_points_blank is False for sq in section.questions)


# ---------------------------------------------------------------------------
# total_score
# ---------------------------------------------------------------------------


def test_total_score_is_none_when_no_points_resolved() -> None:
    assert total_score({}) is None


def test_total_score_sums_resolved_values_including_overrides() -> None:
    # 2 single_choice at the 5-point type default + 1 true_false overridden to 3.
    assert total_score({1: 5, 2: 5, 3: 3}) == 13
