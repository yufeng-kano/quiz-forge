"""Filesystem layout for exported exam papers under `DATA_DIR/exports`
(docker-compose.yml mounts `data/container-mounts/exports` there).

Paths are deterministic from `(data_dir, export_id)` — the `export_id` only
exists once the `exports` row is inserted, so these are computed after that
insert (see `backend.export.job`), mirroring the ingestion-side convention
in `backend.ingestion.storage`.
"""

from pathlib import Path


def export_dir(data_dir: Path) -> Path:
    """Root directory for every exported exam paper file."""
    return data_dir / "exports"


def questions_docx_path(data_dir: Path, export_id: int) -> Path:
    """Where the 題目卷 (questions-only) file for one export is stored."""
    return export_dir(data_dir) / f"{export_id}-questions.docx"


def answers_docx_path(data_dir: Path, export_id: int) -> Path:
    """Where the 答案卷 (questions + answers) file for one export is stored."""
    return export_dir(data_dir) / f"{export_id}-answers.docx"
