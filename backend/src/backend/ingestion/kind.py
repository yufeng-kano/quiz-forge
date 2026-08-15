"""Classify an uploaded file into pdf/image/word by extension.

Single source of truth for "what kind of upload is this" — used both by the
upload API (reject unsupported extensions with 400 before touching disk) and
by the `parse_document` job handler (pick the right extraction branch).
"""

from pathlib import Path
from typing import Literal, get_args

UploadKind = Literal["pdf", "image", "word"]

_EXTENSION_KIND: dict[str, UploadKind] = {
    ".pdf": "pdf",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".docx": "word",
}


class UnsupportedUploadError(ValueError):
    """Raised when a filename's extension isn't one of docs/ingestion.md's supported kinds."""


def detect_upload_kind(filename: str) -> UploadKind:
    """Map `filename`'s extension to an `UploadKind`, or raise `UnsupportedUploadError`."""
    ext = Path(filename).suffix.lower()
    kind = _EXTENSION_KIND.get(ext)
    if kind is None:
        supported = ", ".join(sorted(_EXTENSION_KIND))
        raise UnsupportedUploadError(
            f"unsupported upload file extension {ext or '(none)'!r} for {filename!r}; "
            f"supported: {supported}"
        )
    return kind


assert set(get_args(UploadKind)) == set(_EXTENSION_KIND.values())
