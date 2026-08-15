"""URL fetch + main-content extraction (docs/ingestion.md — 網址輸入線).

`trafilatura` extracts the article body as Markdown entirely locally (no LLM
cost); the pipeline layers exactly one `TEXT_MODEL` call on top of that to
produce BOTH `documents.title` and `documents.summary` in a single
structured call (docs/ingestion.md 網頁線的摘要用途界定 — 不多花一次呼叫).
The summary half is explicitly ONLY for classification/list display, never
for question generation; the title half overwrites the URL/metadata-derived
fallback title (`derive_webpage_title`) that ran before this call.

Both functions do blocking network/parsing work — callers must run them via
`asyncio.to_thread`.
"""

from urllib.parse import unquote, urlparse

import trafilatura
from pydantic import BaseModel

from backend.ingestion.prompts import TITLE_AND_SUMMARY_PROMPT_TEMPLATE
from backend.llm.client import LLMClient


class WebExtractionError(RuntimeError):
    """Raised when a URL can't be fetched or trafilatura finds no extractable content."""


def fetch_html(url: str) -> str:
    """Download `url`'s HTML. Raises `WebExtractionError` if the fetch fails."""
    html = trafilatura.fetch_url(url)
    if not html:
        raise WebExtractionError(f"could not fetch {url!r}")
    return html


def extract_main_content(html: str, url: str) -> tuple[str, str | None]:
    """Extract `html`'s main content as Markdown, plus its title if trafilatura found one.

    Raises `WebExtractionError` if trafilatura can't find extractable main
    content (e.g. a listing page with no article body).
    """
    markdown = trafilatura.extract(html, output_format="markdown", url=url, with_metadata=False)
    if not markdown:
        raise WebExtractionError(f"trafilatura found no extractable main content in {url!r}")

    metadata = trafilatura.extract_metadata(html, default_url=url)
    title = metadata.title if metadata is not None and metadata.title else None
    return markdown.strip(), title


def derive_webpage_title(url: str, *, metadata_title: str | None, max_length: int) -> str:
    """The document title for a 網址（網頁）document, in priority order:

    1. `metadata_title` — the page's own title, as trafilatura's metadata
       extraction found it (`extract_main_content`'s second return value). A
       real, human-authored title always beats anything derived from the
       URL itself.
    2. The URL path's last non-empty segment, percent-decoded (`unquote`) so
       a title like `%E5%85%89%E5%90%88%E4%BD%9C%E7%94%A8` renders as
       `光合作用` instead of raw percent-encoded gibberish — most blog/CMS
       URLs put a readable slug there even when the page has no `<title>`/
       OpenGraph metadata at all.
    3. The bare hostname, when the URL has no path segment either (e.g. a
       bare site root).

    Every candidate is capped at `max_length` characters — even a real page
    title can be unreasonably long, and `documents.title` is a display
    field, not free-form storage.
    """
    if metadata_title and metadata_title.strip():
        return metadata_title.strip()[:max_length]

    parsed = urlparse(url)
    path_segments = [segment for segment in parsed.path.split("/") if segment]
    if path_segments:
        decoded = unquote(path_segments[-1]).strip()
        if decoded:
            return decoded[:max_length]

    if parsed.hostname:
        return parsed.hostname[:max_length]

    return url[:max_length]


class TitleAndSummaryResult(BaseModel):
    """The exact `response_format: json_schema` shape for the URL title+
    summary call — `{title, summary}`, produced by one `TEXT_MODEL` call
    (docs/ingestion.md 網頁線的摘要用途界定)."""

    title: str
    summary: str


async def generate_title_and_summary(llm: LLMClient, content: str) -> TitleAndSummaryResult:
    """One `TEXT_MODEL` json_schema call producing both `documents.title`
    (LLM-authored; the caller trims/caps it and decides what to do if it
    comes back blank) and `documents.summary`.

    docs/ingestion.md is explicit that the summary is ONLY for
    classification/list display — question generation must always use the
    full chunk content, never this summary.
    """
    return await llm.chat(
        messages=[
            {
                "role": "user",
                "content": TITLE_AND_SUMMARY_PROMPT_TEMPLATE.format(content=content),
            }
        ],
        response_model=TitleAndSummaryResult,
        purpose="summarize_url_document",
    )
