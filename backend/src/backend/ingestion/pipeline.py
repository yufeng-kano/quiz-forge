"""`parse_document` / `parse_page` job handlers — the ingestion pipeline's
entrypoint (docs/ingestion.md), wiring together every other `ingestion.*`
module. Registered against `backend.jobs.registry` so `backend.jobs.worker`
dispatches to these purely by job `kind`.

Resume semantics for `parse_document` (.rule 反偷懶規則 — 最小單位可重試):

- If the document has no `pages` rows yet, the full pipeline runs: render/
  extract every page (one vision call per PDF/image page; a single mammoth
  call for Word; a single trafilatura extraction + summary call for a URL),
  then chunk+classify+embed.
- If `pages` rows already exist (a previous run got at least that far — the
  page loop, once started, never stops partway: a per-page failure is caught
  and recorded as that page's `status`, never raised out of the loop), page
  parsing is NEVER re-run — only the chunk+classify+embed phase re-runs,
  from scratch (any partial chunks a previous failed attempt inserted are
  deleted first, since the chunk split is deterministic from the now-fixed
  page markdown and re-running it whole is simpler and safer than resuming
  mid-chunk).

Single-page retry (`POST /v1/pages/{id}/retry` -> `parse_page`) is a
separate job kind: `parse_document` already reaches a terminal state even
when individual pages failed, so retrying one page can't reuse that job.
"""

import asyncio
import io
import logging
from pathlib import Path

from PIL import Image
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import Settings, get_settings
from backend.ingestion import storage
from backend.ingestion.bbox import bbox_to_pixels
from backend.ingestion.category_gc import gc_unused_categories
from backend.ingestion.chunking import split_markdown_into_chunks
from backend.ingestion.classification import classify_chunk, get_or_create_category
from backend.ingestion.kind import UploadKind, detect_upload_kind
from backend.ingestion.pdf import RenderedPage, load_single_image_page, render_pdf_pages
from backend.ingestion.prompts import VISION_PAGE_PROMPT
from backend.ingestion.url_fetch import (
    classify_url_content,
    derive_filename,
    download_url_file,
    probe_content_type,
)
from backend.ingestion.vision import VisionPageResult, rewrite_figure_placeholders
from backend.ingestion.web import (
    derive_webpage_title,
    extract_main_content,
    fetch_html,
    summarize_content,
)
from backend.ingestion.word import extract_word_markdown
from backend.jobs.context import JobContext
from backend.jobs.registry import register_handler
from backend.llm.client import LLMClient, VisionImage, get_llm_client
from backend.models.asset import Asset
from backend.models.chunk import Chunk
from backend.models.document import Document
from backend.models.page import Page

logger = logging.getLogger(__name__)


def _require_int(payload: dict[str, object], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int):
        raise ValueError(f"job payload missing integer {key!r}: {payload!r}")
    return value


@register_handler("parse_document")
async def parse_document(ctx: JobContext) -> None:
    settings = get_settings()
    llm = get_llm_client()
    session = ctx.session

    document_id = _require_int(ctx.payload, "document_id")
    document = await session.get(Document, document_id)
    if document is None:
        raise ValueError(f"document {document_id} not found")

    document.status = "processing"
    await session.commit()

    try:
        existing_pages = (
            (
                await session.execute(
                    select(Page).where(Page.document_id == document_id).order_by(Page.page_no)
                )
            )
            .scalars()
            .all()
        )

        if existing_pages:
            pages = list(existing_pages)
        elif document.source_type == "url":
            pages = await _process_url_document(document, ctx, llm, settings)
        else:
            pages = await _process_upload_document(document, ctx, llm, settings)

        await _run_chunk_phase(document, pages, ctx, llm, settings)

        document.status = "ready"
        await session.commit()
    except Exception:
        document.status = "failed"
        await session.commit()
        raise


@register_handler("parse_page")
async def parse_page(ctx: JobContext) -> None:
    """Re-parse exactly one page, leaving every other page and the
    document's existing chunks untouched (.rule 最小單位可重試)."""
    settings = get_settings()
    llm = get_llm_client()
    session = ctx.session

    page_id = _require_int(ctx.payload, "page_id")
    page = await session.get(Page, page_id)
    if page is None:
        raise ValueError(f"page {page_id} not found")
    document = await session.get(Document, page.document_id)
    if document is None:
        raise ValueError(f"document {page.document_id} not found for page {page_id}")

    page.status = "processing"
    await session.commit()

    try:
        await _delete_page_assets(session, page.id)

        if document.raw_file_path is None:
            # Pure web-page URL (docs/ingestion.md 網址（網頁）) — no file was
            # ever downloaded, so re-parsing means re-fetching + re-extracting.
            if document.source_url is None:
                raise ValueError(f"document {document.id} has source_type=url but no source_url")
            html = await asyncio.to_thread(fetch_html, document.source_url)
            markdown, _title = await asyncio.to_thread(
                extract_main_content, html, document.source_url
            )
            page.markdown = markdown
        elif page.image_path is None:
            # Word — an upload OR a 網址（檔案） URL that resolved to Word:
            # both stored a real `.docx` at `raw_file_path`, so re-extraction
            # is identical either way (docs/ingestion.md ...進上傳檔案同一
            # 條管線).
            page.markdown = await asyncio.to_thread(
                extract_word_markdown, Path(document.raw_file_path)
            )
        else:
            image_bytes = await asyncio.to_thread(Path(page.image_path).read_bytes)
            with Image.open(io.BytesIO(image_bytes)) as opened:
                width, height = opened.size
            result = await llm.vision(
                prompt=VISION_PAGE_PROMPT,
                images=[VisionImage(data=image_bytes, mime_type="image/png")],
                response_model=VisionPageResult,
                purpose="vision_parse_page",
            )
            rendered = RenderedPage(
                page_no=page.page_no, png_bytes=image_bytes, width=width, height=height
            )
            page.markdown = await _crop_figures_and_rewrite(
                document, page, rendered, result, settings, ctx
            )

        page.status = "ready"
        await session.commit()
    except Exception:
        page.status = "failed"
        await session.commit()
        raise


@register_handler("rechunk_document")
async def rechunk_document(ctx: JobContext) -> None:
    """`POST /v1/documents/{id}/rechunk` (docs/ingestion.md 補頁後...手動重
    建) — deletes the document's existing chunks and reruns the chunk/
    classify/embed phase over its *current* page markdown. Page parsing
    itself is never touched here; this reuses `_run_chunk_phase` exactly as
    `parse_document`'s own chunk-phase rerun does (.rule 反偷懶規則 — 不得
    重複核心邏輯), it is only reachable from a different entrypoint (the API
    already checked at least one page is `ready` before enqueueing this)."""
    settings = get_settings()
    llm = get_llm_client()
    session = ctx.session

    document_id = _require_int(ctx.payload, "document_id")
    document = await session.get(Document, document_id)
    if document is None:
        raise ValueError(f"document {document_id} not found")

    pages = (
        (
            await session.execute(
                select(Page).where(Page.document_id == document_id).order_by(Page.page_no)
            )
        )
        .scalars()
        .all()
    )
    if not any(page.status == "ready" for page in pages):
        raise ValueError(f"document {document_id} has no ready page to rechunk from")

    document.status = "processing"
    await session.commit()

    try:
        await _run_chunk_phase(document, list(pages), ctx, llm, settings)
        document.status = "ready"
        await session.commit()
    except Exception:
        document.status = "failed"
        await session.commit()
        raise


async def _delete_page_assets(session: AsyncSession, page_id: int) -> None:
    """Delete `page_id`'s existing asset rows and files before re-parsing it."""
    old_assets = (
        (await session.execute(select(Asset).where(Asset.page_id == page_id))).scalars().all()
    )
    if not old_assets:
        return
    for asset in old_assets:
        await asyncio.to_thread(Path(asset.file_path).unlink, missing_ok=True)
    await session.execute(delete(Asset).where(Asset.page_id == page_id))
    await session.commit()


async def _process_upload_document(
    document: Document, ctx: JobContext, llm: LLMClient, settings: Settings
) -> list[Page]:
    if document.raw_file_path is None:
        raise ValueError(f"document {document.id} has source_type=upload but no raw_file_path")
    kind = detect_upload_kind(Path(document.raw_file_path).name)
    return await _process_document_by_kind(document, kind, ctx, llm, settings)


async def _process_document_by_kind(
    document: Document, kind: UploadKind, ctx: JobContext, llm: LLMClient, settings: Settings
) -> list[Page]:
    """Parse `document.raw_file_path` (already on disk) as `kind` — the one
    path both `source_type=upload` and a `source_type=url` document that
    turned out to point at a file (docs/ingestion.md 網址（檔案）...進上傳
    檔案同一條管線) end up running; the only difference between the two
    origins is how `raw_file_path` got populated."""
    session = ctx.session
    if document.raw_file_path is None:
        raise ValueError(f"document {document.id} has no raw_file_path to parse")
    raw_path = Path(document.raw_file_path)

    if kind == "word":
        markdown = await asyncio.to_thread(extract_word_markdown, raw_path)
        page = Page(document_id=document.id, page_no=1, markdown=markdown, status="ready")
        session.add(page)
        await session.commit()
        await session.refresh(page)
        await ctx.set_progress("1/1 pages")
        return [page]

    file_bytes = await asyncio.to_thread(raw_path.read_bytes)
    if kind == "pdf":
        rendered_pages = await asyncio.to_thread(render_pdf_pages, file_bytes, settings.ocr_dpi)
    else:
        rendered_pages = [await asyncio.to_thread(load_single_image_page, file_bytes)]

    total = len(rendered_pages)
    pages: list[Page] = []
    for rendered in rendered_pages:
        page = await _process_rendered_page(document, rendered, ctx, llm, settings)
        pages.append(page)
        await ctx.set_progress(f"{rendered.page_no}/{total} pages")
    return pages


async def _process_rendered_page(
    document: Document,
    rendered: RenderedPage,
    ctx: JobContext,
    llm: LLMClient,
    settings: Settings,
) -> Page:
    session = ctx.session
    image_path = storage.page_image_path(settings.data_dir, document.id, rendered.page_no)
    image_path.parent.mkdir(parents=True, exist_ok=True)
    await asyncio.to_thread(image_path.write_bytes, rendered.png_bytes)

    page = Page(
        document_id=document.id,
        page_no=rendered.page_no,
        image_path=str(image_path),
        status="processing",
    )
    session.add(page)
    await session.commit()
    await session.refresh(page)

    try:
        result = await llm.vision(
            prompt=VISION_PAGE_PROMPT,
            images=[VisionImage(data=rendered.png_bytes, mime_type="image/png")],
            response_model=VisionPageResult,
            purpose="vision_parse_page",
        )
        page.markdown = await _crop_figures_and_rewrite(
            document, page, rendered, result, settings, ctx
        )
        page.status = "ready"
    except Exception:
        # A single page's vision/crop failure must not abort the rest of the
        # document (docs/ingestion.md 單頁失敗單頁重試；.rule 反偷懶規則 —
        # 禁止部分處理：every remaining page still gets attempted below).
        # Logged in full (never swallowed); the page itself is left `failed`
        # and independently retryable via `POST /v1/pages/{id}/retry`.
        logger.exception("page %d of document %d failed to parse", rendered.page_no, document.id)
        page.status = "failed"

    await session.commit()
    return page


async def _crop_figures_and_rewrite(
    document: Document,
    page: Page,
    rendered: RenderedPage,
    result: VisionPageResult,
    settings: Settings,
    ctx: JobContext,
) -> str:
    if not result.figures:
        return result.markdown

    session = ctx.session
    replacements: dict[str, str] = {}
    with Image.open(io.BytesIO(rendered.png_bytes)) as opened:
        full_image = opened.convert("RGB")

    for index, figure in enumerate(result.figures, start=1):
        box = bbox_to_pixels(figure.bbox, width=rendered.width, height=rendered.height)
        cropped = await asyncio.to_thread(full_image.crop, box)

        asset_path = storage.asset_file_path(settings.data_dir, document.id, page.id, index)
        asset_path.parent.mkdir(parents=True, exist_ok=True)
        buffer = io.BytesIO()
        await asyncio.to_thread(cropped.save, buffer, "PNG")
        await asyncio.to_thread(asset_path.write_bytes, buffer.getvalue())

        asset = Asset(
            page_id=page.id,
            bbox=list(figure.bbox),
            file_path=str(asset_path),
            caption=figure.caption,
        )
        session.add(asset)
        await session.commit()
        await session.refresh(asset)

        replacements[figure.id] = f"![{figure.caption}](/api/v1/assets/{asset.id})"

    return rewrite_figure_placeholders(result.markdown, replacements)


async def _process_url_document(
    document: Document, ctx: JobContext, llm: LLMClient, settings: Settings
) -> list[Page]:
    """docs/ingestion.md 網址（檔案）／網址（網頁）— decide, from the actual
    response Content-Type (falling back to the URL's extension), whether
    `document.source_url` points at a downloadable file or a web page, and
    dispatch to the matching branch below."""
    if document.source_url is None:
        raise ValueError(f"document {document.id} has source_type=url but no source_url")

    content_type, final_url = await asyncio.to_thread(
        probe_content_type, document.source_url, settings.url_fetch_timeout_seconds
    )
    kind = classify_url_content(content_type, final_url)

    if kind is None:
        return await _process_url_webpage(document, ctx, llm, settings)
    return await _process_url_file(document, kind, final_url, ctx, llm, settings)


async def _process_url_webpage(
    document: Document, ctx: JobContext, llm: LLMClient, settings: Settings
) -> list[Page]:
    """docs/ingestion.md 網址（網頁）— trafilatura extracts the article body
    locally, one `TEXT_MODEL` call produces the classification/list-only
    summary."""
    session = ctx.session
    assert document.source_url is not None  # checked by `_process_url_document`

    html = await asyncio.to_thread(fetch_html, document.source_url)
    markdown, metadata_title = await asyncio.to_thread(
        extract_main_content, html, document.source_url
    )
    if document.title == document.source_url:
        # No custom title was given at creation (`POST /v1/documents/url`
        # falls back to the raw URL string when none is given) — derive a
        # human-readable one instead of leaving the raw, often
        # percent-encoded URL as the title.
        document.title = derive_webpage_title(
            document.source_url,
            metadata_title=metadata_title,
            max_length=settings.webpage_title_max_length,
        )

    page = Page(document_id=document.id, page_no=1, markdown=markdown, status="ready")
    session.add(page)
    await session.commit()
    await session.refresh(page)
    await ctx.set_progress("1/1 pages")

    # docs/ingestion.md — this summary is ONLY for classification/list
    # display; question generation must always use full chunk content.
    document.summary = await summarize_content(llm, markdown)
    await session.commit()
    return [page]


async def _process_url_file(
    document: Document,
    kind: UploadKind,
    final_url: str,
    ctx: JobContext,
    llm: LLMClient,
    settings: Settings,
) -> list[Page]:
    """docs/ingestion.md 網址（檔案）— download the file (capped at
    `URL_FETCH_MAX_BYTES`), record it exactly like an upload would
    (`raw_file_path`, a filename-derived title when none was given), then
    reuse `_process_document_by_kind` — the exact same per-kind parse path
    an uploaded file of that kind takes (.rule 反偷懶規則 — 不得重複核心邏輯).
    `source_type` stays `url`; `source_url` is left as the original URL."""
    session = ctx.session
    file_bytes = await asyncio.to_thread(
        download_url_file,
        final_url,
        max_bytes=settings.url_fetch_max_bytes,
        timeout=settings.url_fetch_timeout_seconds,
    )
    filename = derive_filename(final_url, kind)

    dest_path = storage.raw_file_path(settings.data_dir, document.id, filename)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    await asyncio.to_thread(dest_path.write_bytes, file_bytes)

    document.raw_file_path = str(dest_path)
    if document.title == document.source_url:
        # No custom title was given at creation (`POST /v1/documents/url`
        # falls back to the raw URL string) — now that a real file is on
        # disk, a filename beats the bare URL as a title.
        document.title = filename
    await session.commit()

    return await _process_document_by_kind(document, kind, ctx, llm, settings)


async def _run_chunk_phase(
    document: Document,
    pages: list[Page],
    ctx: JobContext,
    llm: LLMClient,
    settings: Settings,
) -> None:
    session = ctx.session

    # Rerun-from-scratch retry: drop any chunks a previous failed attempt
    # already inserted (see module docstring — chunk phase reruns whole, page
    # parsing never does).
    await session.execute(delete(Chunk).where(Chunk.document_id == document.id))
    await session.commit()

    ready_pages = sorted(
        (p for p in pages if p.status == "ready" and p.markdown), key=lambda p: p.page_no
    )
    full_markdown = "\n\n".join(p.markdown or "" for p in ready_pages)
    chunk_texts = split_markdown_into_chunks(full_markdown, settings.chunk_max_chars)

    total = len(chunk_texts)
    for index, content in enumerate(chunk_texts, start=1):
        classification = await classify_chunk(llm, session, content, settings)
        subject = await get_or_create_category(session, classification.subject, parent_id=None)
        topic = await get_or_create_category(session, classification.topic, parent_id=subject.id)
        [embedding] = await llm.embed(texts=[content], purpose="embed_chunk")

        # `chunks` has no dedicated difficulty column (docs/data-model.md) —
        # classification.difficulty is folded into tags[] instead of being
        # dropped.
        tags = [*classification.tags, f"難度:{classification.difficulty}"]

        chunk = Chunk(
            document_id=document.id,
            content=content,
            category_id=topic.id,
            tags=tags,
            embedding=embedding,
        )
        session.add(chunk)
        await session.commit()
        await ctx.set_progress(f"chunks {index}/{total}")

    # The chunks just deleted above may have been the last reference to some
    # category (e.g. reclassification renamed a topic) — GC once the new
    # chunk set is settled, same as `DELETE /v1/documents/{id}`
    # (docs/ingestion.md 文件刪除; .rule 反偷懶規則 不得重複核心邏輯).
    await gc_unused_categories(session)
    await session.commit()
