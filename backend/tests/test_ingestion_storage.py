"""`backend.ingestion.storage` — deterministic `DATA_DIR` path layout.

Every path must be a pure function of `(data_dir, document_id, ...)` — no
randomness — so `DELETE /v1/documents/{id}` can clean up by directory instead
of tracking individual file paths.
"""

from pathlib import Path

from backend.ingestion import storage


def test_raw_file_path_strips_client_supplied_path_components() -> None:
    data_dir = Path("/data")
    path = storage.raw_file_path(data_dir, document_id=7, original_filename="../../etc/passwd")
    assert path == Path("/data/uploads/7/source__passwd")


def test_page_image_path_is_zero_padded_and_deterministic() -> None:
    data_dir = Path("/data")
    path = storage.page_image_path(data_dir, document_id=3, page_no=2)
    assert path == Path("/data/uploads/3/pages/page-002.png")
    assert storage.page_image_path(data_dir, document_id=3, page_no=2) == path


def test_asset_file_path_is_unique_per_page_and_index() -> None:
    data_dir = Path("/data")
    first = storage.asset_file_path(data_dir, document_id=1, page_id=10, index=1)
    second = storage.asset_file_path(data_dir, document_id=1, page_id=10, index=2)
    third = storage.asset_file_path(data_dir, document_id=1, page_id=11, index=1)
    assert first != second
    assert first != third
    assert first.parent == storage.document_asset_dir(data_dir, document_id=1)


def test_document_upload_dir_and_asset_dir_are_scoped_per_document() -> None:
    data_dir = Path("/data")
    assert storage.document_upload_dir(data_dir, 5) == Path("/data/uploads/5")
    assert storage.document_asset_dir(data_dir, 5) == Path("/data/assets/5")
