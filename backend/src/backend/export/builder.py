"""`ExamPaperBuilder` — assembles the 題目卷/答案卷 pair one question at a
time (docs/export.md 每次匯出產生兩份 .docx).

Rendering one question into both papers per call (rather than building each
paper in one pass over the whole list) is what lets the `export_docx` job
handler report progress after every question, matching every other
LLM-batch job handler in this codebase (`generate_questions`) instead of
reporting only "0%"/"100%". The job handler (`backend.export.job`) owns the
section grouping (`backend.export.sections.build_sections`) and drives this
builder section-by-section, question-by-question; this class only ever
renders what it's told, in the order it's told.

All of `python-docx` is synchronous/CPU-bound; every method here does real
work when called and is meant to be invoked through `asyncio.to_thread` from
the (async) job handler — this module itself has no `asyncio` awareness.
"""

from pathlib import Path

from docx import Document as new_document
from docx.document import Document

from backend.export import style
from backend.export.paper import apply_page_setup
from backend.export.renderers import render_question
from backend.questions.schemas import QuestionModel

TITLE_QUESTIONS = "題目卷"
TITLE_ANSWERS = "答案卷"


def _new_paper(
    paper_size: str, exam_title: str, mode_label: str, header_fields: style.HeaderFields
) -> Document:
    """A fresh paper with the full docs/export.md 卷首 header already in
    place: the exam's own title (dominant), the 題目卷/答案卷 label under
    it, and the 班級／座號／姓名 student-info line — the line only shows the
    `header_fields` subset that's checked, and is omitted entirely when none
    are (docs/export.md 卷首：...學生資訊列)."""
    document = new_document()
    apply_page_setup(document, paper_size)
    style.apply_base_style(document)
    style.add_title(document, exam_title)
    style.add_subtitle(document, mode_label)
    style.add_student_info_line(document, header_fields)
    return document


class ExamPaperBuilder:
    """Owns one in-progress 題目卷/答案卷 pair for a single `paper_size` and
    `title` (docs/export.md 卷首：考卷標題)."""

    def __init__(
        self,
        paper_size: str,
        title: str,
        header_fields: style.HeaderFields = style.DEFAULT_HEADER_FIELDS,
    ) -> None:
        self.paper_size = paper_size
        self.title = title
        self.header_fields = header_fields
        self.question_doc: Document = _new_paper(paper_size, title, TITLE_QUESTIONS, header_fields)
        self.answer_doc: Document = _new_paper(paper_size, title, TITLE_ANSWERS, header_fields)

    def add_total_score(self, total: int) -> None:
        """卷首總分 (docs/export.md 任一題有配分且 score 開啟時印總分) — the
        job handler calls this once, right after construction, only when at
        least one question actually resolved to points *and*
        `header_fields.score` is on."""
        style.add_total_score_line(self.question_doc, total)
        style.add_total_score_line(self.answer_doc, total)

    def add_section_heading(self, heading: str) -> None:
        """One 分節 heading (docs/export.md 一、選擇題...), printed
        identically on both papers before that section's questions."""
        style.add_section_heading(self.question_doc, heading)
        style.add_section_heading(self.answer_doc, heading)

    def render_question(
        self,
        number: int,
        question: QuestionModel,
        *,
        show_points_blank: bool = True,
        points_suffix: int | None = None,
    ) -> None:
        """Render one already-validated question, numbered `number` *within
        its section* (docs/export.md 節內連續編號), into both papers —
        `questions` mode into the 題目卷, `answers` mode (stem +
        answer/explanation) into the 答案卷."""
        render_question(
            self.question_doc,
            number,
            question,
            "questions",
            show_points_blank=show_points_blank,
            points_suffix=points_suffix,
        )
        render_question(
            self.answer_doc,
            number,
            question,
            "answers",
            show_points_blank=show_points_blank,
            points_suffix=points_suffix,
        )

    def save(self, questions_path: Path, answers_path: Path) -> None:
        questions_path.parent.mkdir(parents=True, exist_ok=True)
        answers_path.parent.mkdir(parents=True, exist_ok=True)
        self.question_doc.save(str(questions_path))
        self.answer_doc.save(str(answers_path))
