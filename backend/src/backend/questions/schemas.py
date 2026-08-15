"""The six question-type payload schemas (docs/question-bank.md).

One Pydantic model per type — `ComparisonQuestion`, `AnalogyQuestion`,
`SingleChoiceQuestion`, `TrueFalseQuestion`, `FillBlankQuestion`,
`ShortAnswerQuestion` — each carrying a `type: Literal[...]` discriminator
field. This single definition per type serves three purposes at once:

1. **LLM structured output** — `backend.questions.generation` passes the
   type's model class straight to `LLMClient.chat(response_model=...)`,
   which builds its strict `response_format: json_schema` via
   `backend.llm.schema.build_strict_json_schema`.
2. **API validation** — `PATCH /v1/questions/{id}` re-validates an edited
   payload through the same model (`parse_question`), so a shape violation
   is rejected the same way regardless of whether the JSON came from the
   LLM or from a human editor.
3. **Word renderer input** (docs/export.md, future work) — a render
   function per type takes the validated model directly; adding a seventh
   question type is one new model + one new render function, no migration.

`questions.payload` (the jsonb column) stores each type's fields *without*
the `type` key — `type` already lives in `questions.type`, a first-class
column, so keeping it out of the jsonb avoids storing the same fact twice.
`dump_payload`/`parse_question` are the two ends of that: `dump_payload`
strips `type` before a model goes into the column, `parse_question` puts it
back (from the caller-supplied type string, e.g. `questions.type`) so the
stored dict validates again. The discriminated union (`QuestionUnion`,
`QuestionAdapter`) is the real multi-type entry point — e.g. for a generic
"validate whatever `type` says this is" path — while `QUESTION_TYPE_MODELS`
is the direct type-string -> model-class lookup callers use when they
already know the type (the job handler knows it from the request; the API
knows it from the existing row).
"""

from typing import Annotated, Literal, cast

from pydantic import BaseModel, Field, TypeAdapter, model_validator

QuestionType = Literal[
    "comparison", "analogy", "single_choice", "true_false", "fill_blank", "short_answer"
]


class ComparisonDifference(BaseModel):
    aspect: str
    a: str
    b: str


class ComparisonModelAnswer(BaseModel):
    similarities: list[str]
    differences: list[ComparisonDifference]

    @model_validator(mode="after")
    def _differences_non_empty(self) -> "ComparisonModelAnswer":
        if not self.differences:
            raise ValueError("comparison model_answer.differences must not be empty")
        return self


class ComparisonQuestion(BaseModel):
    """比較題 — docs/question-bank.md `comparison`.

    Answer is structured as a similarities/differences table (rendered
    aspect x A x B on the answer sheet), not free text.
    """

    type: Literal["comparison"] = "comparison"
    stem: str
    subject_a: str
    subject_b: str
    aspects: list[str]
    model_answer: ComparisonModelAnswer

    @model_validator(mode="after")
    def _aspects_non_empty(self) -> "ComparisonQuestion":
        if not self.aspects:
            raise ValueError("comparison.aspects must not be empty")
        return self


class AnalogyQuestion(BaseModel):
    """類比題 — docs/question-bank.md `analogy`.

    No `stem` is stored: the renderer builds "A 之於 B，猶如 C 之於＿＿" from
    the a/b/c slots so every analogy question has an identical stem shape.
    `options=None` renders as fill-in-the-blank; a populated `options`
    renders as single-choice.
    """

    type: Literal["analogy"] = "analogy"
    a: str
    b: str
    c: str
    answer: str
    options: list[str] | None = None
    explanation: str | None = None

    @model_validator(mode="after")
    def _options_contain_answer(self) -> "AnalogyQuestion":
        if self.options is not None:
            if len(self.options) < 2:
                raise ValueError("analogy.options must have at least 2 entries when provided")
            if self.answer not in self.options:
                raise ValueError("analogy.answer must be one of analogy.options when provided")
        return self


class SingleChoiceQuestion(BaseModel):
    """單選題 — docs/question-bank.md `single_choice`."""

    type: Literal["single_choice"] = "single_choice"
    stem: str
    options: list[str]
    answer_index: int
    explanation: str | None = None

    @model_validator(mode="after")
    def _answer_index_in_range(self) -> "SingleChoiceQuestion":
        if len(self.options) < 2:
            raise ValueError("single_choice.options must have at least 2 entries")
        if not (0 <= self.answer_index < len(self.options)):
            raise ValueError(
                f"single_choice.answer_index {self.answer_index} is out of range "
                f"for {len(self.options)} options"
            )
        return self


class TrueFalseQuestion(BaseModel):
    """是非題 — docs/question-bank.md `true_false`."""

    type: Literal["true_false"] = "true_false"
    stem: str
    answer: bool
    explanation: str | None = None


class FillBlankQuestion(BaseModel):
    """填充題 — docs/question-bank.md `fill_blank`.

    `stem` marks each blank with a `____` token; `answers` supplies them in
    left-to-right order, so the two must have matching lengths.
    """

    type: Literal["fill_blank"] = "fill_blank"
    stem: str
    answers: list[str]

    @model_validator(mode="after")
    def _answers_match_blanks(self) -> "FillBlankQuestion":
        blank_count = self.stem.count("____")
        if blank_count == 0:
            raise ValueError("fill_blank.stem must contain at least one '____' blank marker")
        if blank_count != len(self.answers):
            raise ValueError(
                f"fill_blank.stem has {blank_count} blank marker(s) but "
                f"answers has {len(self.answers)} entr(ies)"
            )
        return self


class ShortAnswerQuestion(BaseModel):
    """問答題 — docs/question-bank.md `short_answer`."""

    type: Literal["short_answer"] = "short_answer"
    stem: str
    model_answer: str
    key_points: list[str]

    @model_validator(mode="after")
    def _key_points_non_empty(self) -> "ShortAnswerQuestion":
        if not self.key_points:
            raise ValueError("short_answer.key_points must not be empty")
        return self


QUESTION_TYPE_MODELS: dict[str, type[BaseModel]] = {
    "comparison": ComparisonQuestion,
    "analogy": AnalogyQuestion,
    "single_choice": SingleChoiceQuestion,
    "true_false": TrueFalseQuestion,
    "fill_blank": FillBlankQuestion,
    "short_answer": ShortAnswerQuestion,
}

# Plain union (no discriminator metadata) — the precise return type of
# `parse_question`, so a caller that already validated a payload can access
# `.type` or any other field without narrowing first.
type QuestionModel = (
    ComparisonQuestion
    | AnalogyQuestion
    | SingleChoiceQuestion
    | TrueFalseQuestion
    | FillBlankQuestion
    | ShortAnswerQuestion
)

# Same union, tagged for Pydantic's discriminated-union machinery — the
# actual "pick a branch from `type`" entry point (`QuestionAdapter` below).
QuestionUnion = Annotated[QuestionModel, Field(discriminator="type")]

QuestionAdapter: TypeAdapter[QuestionModel] = TypeAdapter(QuestionUnion)


def payload_model_for_type(question_type: str) -> type[BaseModel]:
    """The Pydantic model class for `question_type` (unvalidated string in, e.g.
    from a job payload or query param). Raises `ValueError` for an unknown type."""
    try:
        return QUESTION_TYPE_MODELS[question_type]
    except KeyError:
        raise ValueError(f"unknown question type {question_type!r}") from None


def parse_question(question_type: str, payload: dict[str, object]) -> QuestionModel:
    """Validate `payload` (as stored in `questions.payload`, no `type` key) against
    `question_type`'s model. Raises `pydantic.ValidationError` on a shape violation —
    callers turn that into an API 422 or a job-handler failure as appropriate.

    `payload_model_for_type` picks the model class dynamically from a plain
    `str`, so the type checker can't itself narrow the result to `QuestionModel`
    the way it could from a literal branch — the `cast` documents what
    `QUESTION_TYPE_MODELS` guarantees by construction (every value in it *is*
    a `QuestionModel` member), it does not widen anything to `Any`.
    """
    model_cls = payload_model_for_type(question_type)
    validated = model_cls.model_validate({**payload, "type": question_type})
    return cast(QuestionModel, validated)


def dump_payload(question: BaseModel) -> dict[str, object]:
    """The jsonb-ready dict for a validated question model — every field except
    the `type` discriminator, which lives in `questions.type` instead."""
    return question.model_dump(mode="json", exclude={"type"})
