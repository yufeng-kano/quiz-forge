"""Word exam-paper export (docs/export.md).

- `backend.export.paper` — supported paper sizes (mm constants) + page setup.
- `backend.export.style` — centralized fonts/sizes/line spacing + shared
  paragraph/table helpers, so no render function touches font properties
  directly.
- `backend.export.renderers` — one render function per question type, input
  is that type's Pydantic model from `backend.questions.schemas` (the same
  single definition used for LLM output and API validation).
- `backend.export.builder` — `ExamPaperBuilder` assembles the 題目卷/答案卷
  pair question-by-question (so a job handler can report per-question
  progress) and saves both to disk.
- `backend.export.paths` — deterministic `DATA_DIR/exports/...` file layout.
- `backend.export.job` — the `export_docx` job handler.
"""
