"""`ExamPaperBuilder` — assembles the 題目卷/答案卷 pair one question at a
time (docs/export.md 每次匯出產生兩份 .docx).

Rendering one question into both papers per call (rather than building each
paper in one pass over the whole list) is what lets the `export_docx` job
handler report progress after every question, matching every other
LLM-batch job handler in this codebase (`generate_questions`) instead of
reporting only "0%"/"100%".

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


def _new_paper(paper_size: str, title: str) -> Document:
    document = new_document()
    apply_page_setup(document, paper_size)
    style.apply_base_style(document)
    style.add_title(document, title)
    return document


class ExamPaperBuilder:
    """Owns one in-progress 題目卷/答案卷 pair for a single `paper_size`."""

    def __init__(self, paper_size: str) -> None:
        self.paper_size = paper_size
        self.question_doc: Document = _new_paper(paper_size, TITLE_QUESTIONS)
        self.answer_doc: Document = _new_paper(paper_size, TITLE_ANSWERS)

    def render_question(self, number: int, question: QuestionModel) -> None:
        """Render one already-validated question, numbered `number`, into
        both papers — `questions` mode into the 題目卷, `answers` mode
        (stem + answer/explanation) into the 答案卷."""
        render_question(self.question_doc, number, question, "questions")
        render_question(self.answer_doc, number, question, "answers")

    def save(self, questions_path: Path, answers_path: Path) -> None:
        questions_path.parent.mkdir(parents=True, exist_ok=True)
        answers_path.parent.mkdir(parents=True, exist_ok=True)
        self.question_doc.save(str(questions_path))
        self.answer_doc.save(str(answers_path))
