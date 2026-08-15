"""`backend.questions.schemas` — the six question-type payload schemas
(.rule 反偷懶規則: 題型 schema 驗證屬高風險邏輯，必須有測試).

Covers per-type valid/invalid shapes, the discriminated-union round-trip
through `parse_question`/`dump_payload` (mirrors how a `questions.payload`
jsonb value round-trips), and that `QuestionAdapter` — the literal
discriminated union, not just the type-string lookup table — picks the
right branch from a `type` key.
"""

import pytest
from pydantic import ValidationError

from backend.questions.schemas import (
    QUESTION_TYPE_MODELS,
    AnalogyQuestion,
    ComparisonQuestion,
    FillBlankQuestion,
    QuestionAdapter,
    ShortAnswerQuestion,
    SingleChoiceQuestion,
    TrueFalseQuestion,
    dump_payload,
    parse_question,
    payload_model_for_type,
)

# ---------------------------------------------------------------------------
# comparison
# ---------------------------------------------------------------------------


def _valid_comparison_payload() -> dict[str, object]:
    return {
        "stem": "試比較光合作用與呼吸作用之異同。",
        "subject_a": "光合作用",
        "subject_b": "呼吸作用",
        "aspects": ["場所", "能量轉換"],
        "model_answer": {
            "similarities": ["皆為細胞內能量代謝反應"],
            "differences": [{"aspect": "場所", "a": "葉綠體", "b": "粒線體"}],
        },
    }


def test_comparison_accepts_valid_payload() -> None:
    question = ComparisonQuestion.model_validate(_valid_comparison_payload())
    assert question.type == "comparison"
    assert question.model_answer.differences[0].aspect == "場所"


def test_comparison_rejects_empty_aspects() -> None:
    payload = _valid_comparison_payload()
    payload["aspects"] = []
    with pytest.raises(ValidationError):
        ComparisonQuestion.model_validate(payload)


def test_comparison_rejects_empty_differences() -> None:
    payload = _valid_comparison_payload()
    payload["model_answer"] = {"similarities": ["同"], "differences": []}
    with pytest.raises(ValidationError):
        ComparisonQuestion.model_validate(payload)


def test_comparison_rejects_missing_field() -> None:
    payload = _valid_comparison_payload()
    del payload["subject_b"]
    with pytest.raises(ValidationError):
        ComparisonQuestion.model_validate(payload)


def test_comparison_rejects_malformed_difference_entry() -> None:
    payload = _valid_comparison_payload()
    payload["model_answer"] = {
        "similarities": ["同"],
        # missing "b"
        "differences": [{"aspect": "場所", "a": "葉綠體"}],
    }
    with pytest.raises(ValidationError):
        ComparisonQuestion.model_validate(payload)


# ---------------------------------------------------------------------------
# analogy
# ---------------------------------------------------------------------------


def test_analogy_accepts_fill_in_form_with_null_options() -> None:
    question = AnalogyQuestion.model_validate(
        {"a": "筆", "b": "寫字", "c": "剪刀", "answer": "剪裁", "options": None}
    )
    assert question.options is None


def test_analogy_accepts_single_choice_form_with_options() -> None:
    question = AnalogyQuestion.model_validate(
        {
            "a": "筆",
            "b": "寫字",
            "c": "剪刀",
            "answer": "剪裁",
            "options": ["剪裁", "縫紉", "烹飪", "測量"],
            "explanation": "工具之於其功能",
        }
    )
    assert question.options is not None
    assert question.answer in question.options


def test_analogy_rejects_answer_not_in_options() -> None:
    with pytest.raises(ValidationError):
        AnalogyQuestion.model_validate(
            {
                "a": "筆",
                "b": "寫字",
                "c": "剪刀",
                "answer": "剪裁",
                "options": ["縫紉", "烹飪", "測量"],
            }
        )


def test_analogy_rejects_too_few_options() -> None:
    with pytest.raises(ValidationError):
        AnalogyQuestion.model_validate(
            {"a": "筆", "b": "寫字", "c": "剪刀", "answer": "剪裁", "options": ["剪裁"]}
        )


def test_analogy_has_no_stem_field() -> None:
    # docs/question-bank.md: 類比題不存題幹，只存槽位 -- renderer builds it.
    assert "stem" not in AnalogyQuestion.model_fields


# ---------------------------------------------------------------------------
# single_choice
# ---------------------------------------------------------------------------


def test_single_choice_accepts_valid_payload() -> None:
    question = SingleChoiceQuestion.model_validate(
        {"stem": "...", "options": ["a", "b", "c", "d"], "answer_index": 2}
    )
    assert question.answer_index == 2


def test_single_choice_rejects_answer_index_out_of_range() -> None:
    with pytest.raises(ValidationError):
        SingleChoiceQuestion.model_validate(
            {"stem": "...", "options": ["a", "b"], "answer_index": 2}
        )


def test_single_choice_rejects_negative_answer_index() -> None:
    with pytest.raises(ValidationError):
        SingleChoiceQuestion.model_validate(
            {"stem": "...", "options": ["a", "b"], "answer_index": -1}
        )


def test_single_choice_rejects_too_few_options() -> None:
    with pytest.raises(ValidationError):
        SingleChoiceQuestion.model_validate({"stem": "...", "options": ["a"], "answer_index": 0})


# ---------------------------------------------------------------------------
# true_false
# ---------------------------------------------------------------------------


def test_true_false_accepts_valid_payload() -> None:
    question = TrueFalseQuestion.model_validate({"stem": "...", "answer": True})
    assert question.answer is True


def test_true_false_rejects_non_bool_answer() -> None:
    # pydantic's lax bool coercion accepts strings like "yes"/"true"/"0"; use
    # something genuinely uncoercible to prove the field really is validated.
    with pytest.raises(ValidationError):
        TrueFalseQuestion.model_validate({"stem": "...", "answer": "maybe"})


# ---------------------------------------------------------------------------
# fill_blank
# ---------------------------------------------------------------------------


def test_fill_blank_accepts_matching_blanks_and_answers() -> None:
    question = FillBlankQuestion.model_validate(
        {"stem": "水的化學式為 ____，由 ____ 與氧組成。", "answers": ["H2O", "氫"]}
    )
    assert len(question.answers) == 2


def test_fill_blank_rejects_answer_count_mismatch() -> None:
    with pytest.raises(ValidationError):
        FillBlankQuestion.model_validate(
            {"stem": "水的化學式為 ____，由 ____ 與氧組成。", "answers": ["H2O"]}
        )


def test_fill_blank_rejects_no_blank_markers() -> None:
    with pytest.raises(ValidationError):
        FillBlankQuestion.model_validate({"stem": "水的化學式為 H2O。", "answers": []})


# ---------------------------------------------------------------------------
# short_answer
# ---------------------------------------------------------------------------


def test_short_answer_accepts_valid_payload() -> None:
    question = ShortAnswerQuestion.model_validate(
        {"stem": "...", "model_answer": "...", "key_points": ["重點一", "重點二"]}
    )
    assert len(question.key_points) == 2


def test_short_answer_rejects_empty_key_points() -> None:
    with pytest.raises(ValidationError):
        ShortAnswerQuestion.model_validate({"stem": "...", "model_answer": "...", "key_points": []})


# ---------------------------------------------------------------------------
# type-string lookup + discriminated-union round trip
# ---------------------------------------------------------------------------


def test_payload_model_for_type_covers_all_six_types() -> None:
    assert set(QUESTION_TYPE_MODELS) == {
        "comparison",
        "analogy",
        "single_choice",
        "true_false",
        "fill_blank",
        "short_answer",
    }
    for question_type, model_cls in QUESTION_TYPE_MODELS.items():
        assert payload_model_for_type(question_type) is model_cls


def test_payload_model_for_type_rejects_unknown_type() -> None:
    with pytest.raises(ValueError, match="unknown question type"):
        payload_model_for_type("essay")


def test_parse_question_rejects_unknown_type() -> None:
    with pytest.raises(ValueError, match="unknown question type"):
        parse_question("essay", {"stem": "..."})


@pytest.mark.parametrize(
    ("question_type", "payload"),
    [
        ("comparison", _valid_comparison_payload()),
        (
            "analogy",
            {"a": "筆", "b": "寫字", "c": "剪刀", "answer": "剪裁", "options": None},
        ),
        (
            "single_choice",
            {"stem": "...", "options": ["a", "b", "c"], "answer_index": 1},
        ),
        ("true_false", {"stem": "...", "answer": False}),
        (
            "fill_blank",
            {"stem": "答案是 ____。", "answers": ["42"]},
        ),
        (
            "short_answer",
            {"stem": "...", "model_answer": "...", "key_points": ["a"]},
        ),
    ],
)
def test_round_trip_from_jsonb_shaped_dict(
    question_type: str, payload: dict[str, object]
) -> None:
    """Simulates a `questions` row: `type` column + `payload` jsonb (no `type`
    key inside it). `parse_question` must reconstruct the exact same model
    the LLM/API produced, and `dump_payload` must give back a dict equal to
    what was stored — a lossless round trip through the discriminator."""
    validated = parse_question(question_type, payload)
    assert type(validated) is payload_model_for_type(question_type)
    assert validated.type == question_type

    dumped = dump_payload(validated)
    assert "type" not in dumped
    # every field that was in the original payload survives unchanged.
    for key, value in payload.items():
        assert dumped[key] == value

    # dumping then re-parsing must be a fixed point.
    re_parsed = parse_question(question_type, dumped)
    assert dump_payload(re_parsed) == dumped


def test_question_adapter_discriminates_on_type_field() -> None:
    instance = QuestionAdapter.validate_python(
        {"type": "single_choice", "stem": "...", "options": ["a", "b"], "answer_index": 0}
    )
    assert isinstance(instance, SingleChoiceQuestion)


def test_question_adapter_rejects_unknown_discriminator_value() -> None:
    with pytest.raises(ValidationError):
        QuestionAdapter.validate_python({"type": "essay", "stem": "..."})


def test_question_adapter_rejects_shape_that_does_not_match_its_own_type() -> None:
    # claims to be true_false but has single_choice-shaped fields.
    with pytest.raises(ValidationError):
        QuestionAdapter.validate_python(
            {"type": "true_false", "options": ["a", "b"], "answer_index": 0}
        )
