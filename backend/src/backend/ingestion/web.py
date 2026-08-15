"""URL fetch + main-content extraction (docs/ingestion.md — 網址輸入線).

`trafilatura` extracts the article body as Markdown entirely locally (no LLM
cost); the pipeline layers exactly one `TEXT_MODEL` call on top of that to
produce `documents.summary` — which docs/ingestion.md is explicit is ONLY
for classification/list display, never for question generation.

Both functions do blocking network/parsing work — callers must run them via
`asyncio.to_thread`.
"""

import trafilatura
from pydantic import BaseModel

from backend.ingestion.prompts import SUMMARY_PROMPT_TEMPLATE
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


class SummaryResult(BaseModel):
    """The exact `response_format: json_schema` shape for the URL summary call."""

    summary: str


async def summarize_content(llm: LLMClient, content: str) -> str:
    """One `TEXT_MODEL` json_schema call producing `documents.summary`.

    docs/ingestion.md is explicit that this summary is ONLY for
    classification/list display — question generation must always use the
    full chunk content, never this summary.
    """
    result = await llm.chat(
        messages=[{"role": "user", "content": SUMMARY_PROMPT_TEMPLATE.format(content=content)}],
        response_model=SummaryResult,
        purpose="summarize_url_document",
    )
    return result.summary
