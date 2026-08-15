"""Document ingestion pipeline (docs/ingestion.md).

Modules:

- `kind`: classify an uploaded file into pdf/image/word by extension.
- `storage`: `DATA_DIR` filesystem layout for uploads/pages/assets.
- `pdf`: PyMuPDF page rendering + standalone image loading.
- `bbox`: 0-1000 normalized bbox -> pixel-box conversion and cropping.
- `word`: `.docx` -> Markdown extraction (mammoth + markdownify).
- `web`: URL fetch + main-content extraction (trafilatura).
- `chunking`: heading-structure + length-limited Markdown splitting.
- `classification`: chunk subject/topic/difficulty/tags via `TEXT_MODEL`.
- `prompts`: every LLM prompt template used by this package, kept out of
  logic modules so prompt engineering never gets scattered inline.
- `pipeline`: the `parse_document` / `parse_page` job handlers that wire the
  above together end to end.
"""
