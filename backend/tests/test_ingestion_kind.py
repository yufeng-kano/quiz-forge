"""`backend.ingestion.kind` — upload-file-extension classification."""

import pytest

from backend.ingestion.kind import UnsupportedUploadError, detect_upload_kind


@pytest.mark.parametrize(
    ("filename", "expected_kind"),
    [
        ("scan.pdf", "pdf"),
        ("SCAN.PDF", "pdf"),
        ("photo.png", "image"),
        ("photo.jpg", "image"),
        ("photo.jpeg", "image"),
        ("notes.docx", "word"),
    ],
)
def test_detect_upload_kind_by_extension(filename: str, expected_kind: str) -> None:
    assert detect_upload_kind(filename) == expected_kind


def test_detect_upload_kind_rejects_unsupported_extension() -> None:
    with pytest.raises(UnsupportedUploadError):
        detect_upload_kind("archive.zip")


def test_detect_upload_kind_rejects_missing_extension() -> None:
    with pytest.raises(UnsupportedUploadError):
        detect_upload_kind("no-extension")
