"""`/v1/exports` — create export jobs, list history, download docx files
(docs/export.md 選題流程).

Only `POST` creates a `jobs` row; the actual selection-validation and
`python-docx` rendering happen in the background worker
(`backend.export.job`), per .rule 使用者體驗規則 (長任務一律走背景 job)."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_session
from backend.models.export import Export
from backend.models.job import Job
from backend.schemas.export import ExportIn, ExportListItemOut, ExportOut

router = APIRouter(prefix="/exports", tags=["exports"])

_DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@router.post("", response_model=ExportOut, status_code=status.HTTP_201_CREATED)
async def create_export_job(
    body: ExportIn, session: AsyncSession = Depends(get_session)
) -> ExportOut:
    job = Job(
        kind="export_docx",
        payload={
            "question_ids": body.question_ids,
            "paper_size": body.paper_size,
            "title": body.title,
            "points": body.points,
        },
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return ExportOut(job_id=job.id)


@router.get("", response_model=list[ExportListItemOut])
async def list_exports(session: AsyncSession = Depends(get_session)) -> list[ExportListItemOut]:
    exports = (
        (await session.execute(select(Export).order_by(Export.created_at.desc(), Export.id.desc())))
        .scalars()
        .all()
    )
    return [
        ExportListItemOut(
            id=export.id,
            title=export.title,
            paper_size=export.paper_size,
            question_count=len(export.question_ids),
            created_at=export.created_at,
            questions_available=export.docx_path is not None and Path(export.docx_path).exists(),
            answers_available=export.answer_docx_path is not None
            and Path(export.answer_docx_path).exists(),
        )
        for export in exports
    ]


async def _get_export_or_404(export_id: int, session: AsyncSession) -> Export:
    export = await session.get(Export, export_id)
    if export is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="export not found")
    return export


def _file_response(path_str: str | None, *, missing_detail: str, filename: str) -> FileResponse:
    if path_str is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=missing_detail)
    path = Path(path_str)
    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"{missing_detail} (file missing on disk)"
        )
    return FileResponse(path, media_type=_DOCX_MEDIA_TYPE, filename=filename)


@router.get("/{export_id}/questions.docx")
async def download_questions_docx(
    export_id: int, session: AsyncSession = Depends(get_session)
) -> FileResponse:
    export = await _get_export_or_404(export_id, session)
    return _file_response(
        export.docx_path,
        missing_detail="questions docx not ready",
        filename=f"export-{export_id}-題目卷.docx",
    )


@router.get("/{export_id}/answers.docx")
async def download_answers_docx(
    export_id: int, session: AsyncSession = Depends(get_session)
) -> FileResponse:
    export = await _get_export_or_404(export_id, session)
    return _file_response(
        export.answer_docx_path,
        missing_detail="answers docx not ready",
        filename=f"export-{export_id}-答案卷.docx",
    )
