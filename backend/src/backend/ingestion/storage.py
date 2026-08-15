"""Filesystem layout for ingestion artifacts under `DATA_DIR`.

docs/architecture.md only wires up dedicated bind mounts for
`DATA_DIR/uploads`, `DATA_DIR/assets` and `DATA_DIR/exports` — there is no
third mount for rendered page images. Page PNGs are therefore stored as a
working artifact *under* the upload's own directory
(`uploads/{document_id}/pages/`) rather than adding a new bind mount, so
docker-compose.yml doesn't need to change for this feature.

Every path in this module is deterministic from `(data_dir, document_id, ...)`
— nothing here is a random/uuid name — so cleanup (`DELETE /v1/documents/{id}`)
can just `shutil.rmtree` the two per-document directories instead of tracking
individual file paths.
"""

from pathlib import Path


def document_upload_dir(data_dir: Path, document_id: int) -> Path:
    """Root directory for everything derived from one uploaded document."""
    return data_dir / "uploads" / str(document_id)


def raw_file_path(data_dir: Path, document_id: int, original_filename: str) -> Path:
    """Where the originally-uploaded file itself is stored, unmodified."""
    safe_name = Path(original_filename).name  # strip any path components a client might send
    return document_upload_dir(data_dir, document_id) / f"source__{safe_name}"


def page_image_path(data_dir: Path, document_id: int, page_no: int) -> Path:
    """Where one PDF-rendered (or normalized standalone-image) page PNG is stored."""
    return document_upload_dir(data_dir, document_id) / "pages" / f"page-{page_no:03d}.png"


def document_asset_dir(data_dir: Path, document_id: int) -> Path:
    """Root directory for every cropped figure belonging to one document."""
    return data_dir / "assets" / str(document_id)


def asset_file_path(data_dir: Path, document_id: int, page_id: int, index: int) -> Path:
    """Where one cropped figure's PNG is stored."""
    return document_asset_dir(data_dir, document_id) / f"page{page_id}-fig{index:02d}.png"
