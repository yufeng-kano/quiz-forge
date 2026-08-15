"""`.docx` -> Markdown extraction (docs/ingestion.md — Word 用 mammoth 直接抽文字).

No vision call for Word documents: `mammoth` converts the document to HTML
(preserving heading/list/table structure) and `markdownify` turns that HTML
into Markdown, which becomes the single `pages` row for the document.

Blocking I/O (mammoth reads the file, `python-docx`-style parsing underneath)
— callers must run this via `asyncio.to_thread`.
"""

import logging
from pathlib import Path

import mammoth
from markdownify import markdownify

logger = logging.getLogger(__name__)


def extract_word_markdown(path: Path) -> str:
    """Convert the `.docx` at `path` to Markdown via mammoth -> HTML -> markdownify."""
    with path.open("rb") as docx_file:
        result = mammoth.convert_to_html(docx_file)

    for message in result.messages:
        # mammoth reports unsupported-style warnings inline instead of raising;
        # surface them (not swallowed) without failing the whole page on them.
        logger.warning("mammoth conversion warning for %s: %s", path, message.message)

    markdown = markdownify(result.value, heading_style="ATX")
    return markdown.strip()
