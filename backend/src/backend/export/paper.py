"""Paper size + margin constants for exported exam papers (docs/export.md
支援紙張：A4、B4、B3；尺寸常數放設定模組，不寫死在 render 邏輯).

Sizes are the **JIS B-series**, not ISO B-series: docs/export.md notes 台灣
考卷慣用 B4, and in Taiwan/Japan office use "B4"/"B3" conventionally means
the JIS dimensions (257x364mm / 364x515mm) — larger than their ISO
namesakes (250x353mm / 353x500mm). Using ISO sizes here would silently
produce paper nobody in the target market actually loads into a printer.
"""

from typing import Final

from docx.document import Document
from docx.shared import Mm

# {paper size name -> (width_mm, height_mm)}, portrait orientation.
PAPER_SIZES_MM: Final[dict[str, tuple[float, float]]] = {
    "A4": (210.0, 297.0),
    "B4": (257.0, 364.0),
    "B3": (364.0, 515.0),
}

SUPPORTED_PAPER_SIZES: Final[frozenset[str]] = frozenset(PAPER_SIZES_MM)

# Uniform page margin on all four sides, applied to every supported size.
PAGE_MARGIN_MM: Final[float] = 20.0


def paper_dimensions_mm(paper_size: str) -> tuple[float, float]:
    """`(width_mm, height_mm)` for `paper_size`. Raises `ValueError` for an
    unsupported size — callers turn that into a 422 (API) or job failure."""
    try:
        return PAPER_SIZES_MM[paper_size]
    except KeyError:
        raise ValueError(
            f"unsupported paper size {paper_size!r}; supported: {sorted(SUPPORTED_PAPER_SIZES)}"
        ) from None


def apply_page_setup(document: Document, paper_size: str) -> None:
    """Set `document`'s (single, default) section to `paper_size`'s
    dimensions and the standard margin, via python-docx section properties."""
    width_mm, height_mm = paper_dimensions_mm(paper_size)
    section = document.sections[0]
    section.page_width = Mm(width_mm)
    section.page_height = Mm(height_mm)
    section.top_margin = Mm(PAGE_MARGIN_MM)
    section.bottom_margin = Mm(PAGE_MARGIN_MM)
    section.left_margin = Mm(PAGE_MARGIN_MM)
    section.right_margin = Mm(PAGE_MARGIN_MM)
