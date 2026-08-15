"""Heading-structure + length-limited Markdown splitting (docs/ingestion.md Chunk 與分類).

"解析完成的 Markdown 依標題結構 + 長度上限切 chunk": split first at heading
boundaries (any `#`..`######` line) so each chunk stays topically coherent,
then further split any section that's still over `CHUNK_MAX_CHARS` by
paragraph, falling back to a hard character split for a single
over-the-limit paragraph. Never drops content and never returns an empty
chunk.
"""

import re

_HEADING_LINE_RE = re.compile(r"^#{1,6}[ \t]+.*$", re.MULTILINE)
_PARAGRAPH_SPLIT_RE = re.compile(r"\n{2,}")


def _split_by_headings(markdown: str) -> list[str]:
    """Split `markdown` into sections, one per heading (plus a preamble section if any)."""
    matches = list(_HEADING_LINE_RE.finditer(markdown))
    if not matches:
        return [markdown]

    sections: list[str] = []
    preamble = markdown[: matches[0].start()]
    if preamble.strip():
        sections.append(preamble)

    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown)
        sections.append(markdown[start:end])

    return sections


def _hard_split(text: str, max_chars: int) -> list[str]:
    """Split `text` (already known to exceed `max_chars`) at `max_chars` boundaries.

    Prefers cutting on whitespace near the limit (readable for
    space-separated languages); falls back to a raw character cut, which is
    the common case for CJK text that has no word-separating spaces.
    """
    pieces: list[str] = []
    remaining = text
    while len(remaining) > max_chars:
        cut = remaining.rfind(" ", 0, max_chars)
        if cut <= 0:
            cut = max_chars
        piece = remaining[:cut].strip()
        if piece:
            pieces.append(piece)
        remaining = remaining[cut:].strip()
    if remaining:
        pieces.append(remaining)
    return pieces


def _split_long_section(section: str, max_chars: int) -> list[str]:
    """Split one heading-bounded `section` into chunks each within `max_chars`."""
    stripped = section.strip()
    if not stripped:
        return []
    if len(stripped) <= max_chars:
        return [stripped]

    chunks: list[str] = []
    current = ""
    for paragraph in _PARAGRAPH_SPLIT_RE.split(section):
        paragraph = paragraph.strip()
        if not paragraph:
            continue

        candidate = f"{current}\n\n{paragraph}" if current else paragraph
        if len(candidate) <= max_chars:
            current = candidate
            continue

        if current:
            chunks.append(current)
            current = ""

        if len(paragraph) <= max_chars:
            current = paragraph
        else:
            chunks.extend(_hard_split(paragraph, max_chars))

    if current:
        chunks.append(current)
    return chunks


def split_markdown_into_chunks(markdown: str, max_chars: int) -> list[str]:
    """Split `markdown` into ordered, non-empty chunks each at most `max_chars` long.

    First splits at heading boundaries, then further splits any section still
    over the limit by paragraph (and, as a last resort, by raw character
    count for a single over-limit paragraph). Returns `[]` for blank input.
    """
    if max_chars <= 0:
        raise ValueError("max_chars must be positive")
    if not markdown.strip():
        return []

    chunks: list[str] = []
    for section in _split_by_headings(markdown):
        chunks.extend(_split_long_section(section, max_chars))
    return chunks
