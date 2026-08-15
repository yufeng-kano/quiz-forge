"""PDF page rendering and standalone-image loading (docs/ingestion.md Vision 管線).

"PDF/圖片走 vision 管線... 不判斷 PDF 有無文字層，全部走同一條路" — a PDF
is rendered page-by-page to PNG with PyMuPDF at `OCR_DPI`; a standalone image
upload is treated as a single page. Both produce the same `RenderedPage`
shape so the rest of the pipeline doesn't care which source it came from.

Both PyMuPDF and Pillow are CPU-bound/blocking; every public function here is
synchronous on purpose so callers can (and must) run it via
`asyncio.to_thread` instead of blocking the event loop.
"""

import io
from dataclasses import dataclass

import pymupdf
from PIL import Image


@dataclass(frozen=True)
class RenderedPage:
    """One page's full-resolution PNG render, ready for a vision call and cropping."""

    page_no: int
    png_bytes: bytes
    width: int
    height: int


def render_pdf_pages(pdf_bytes: bytes, dpi: int) -> list[RenderedPage]:
    """Render every page of `pdf_bytes` to a PNG at `dpi` (docs/ingestion.md `OCR_DPI`)."""
    document = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    try:
        zoom = dpi / 72.0  # PDF points are 72/inch; PyMuPDF's default render is 72 DPI.
        matrix = pymupdf.Matrix(zoom, zoom)
        pages: list[RenderedPage] = []
        for page_index in range(document.page_count):
            index = page_index + 1
            page = document.load_page(page_index)
            pixmap = page.get_pixmap(matrix=matrix)
            pages.append(
                RenderedPage(
                    page_no=index,
                    png_bytes=pixmap.tobytes("png"),
                    width=pixmap.width,
                    height=pixmap.height,
                )
            )
        return pages
    finally:
        document.close()


def load_single_image_page(image_bytes: bytes) -> RenderedPage:
    """Normalize a standalone image upload to a single `RenderedPage` PNG.

    Re-encodes to PNG regardless of source format (PNG/JPEG) so downstream
    storage and vision-call mime type are uniform.
    """
    with Image.open(io.BytesIO(image_bytes)) as image:
        rgb_image = image.convert("RGB")
        buffer = io.BytesIO()
        rgb_image.save(buffer, format="PNG")
        return RenderedPage(
            page_no=1,
            png_bytes=buffer.getvalue(),
            width=rgb_image.width,
            height=rgb_image.height,
        )
