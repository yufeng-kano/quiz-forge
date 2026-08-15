"""`/v1/folders` — flat, user-managed document-library folders
(docs/ingestion.md 文件管理；docs/data-model.md `folders` 平面資料夾).

Unrelated to `/v1/categories` (LLM knowledge classification, which drives
question-generation scope): folders only affect how a user browses/organizes
the document library. Moving a document in/out of a folder is done through
`PATCH /v1/documents/{id}` (body `{folder_id}`), not here.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_session
from backend.models.document import Document
from backend.models.folder import Folder
from backend.schemas.folder import FolderIn, FolderOut

router = APIRouter(prefix="/folders", tags=["folders"])


async def _get_folder_or_404(folder_id: int, session: AsyncSession) -> Folder:
    folder = await session.get(Folder, folder_id)
    if folder is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="folder not found")
    return folder


async def _document_counts(session: AsyncSession, folder_ids: list[int]) -> dict[int, int]:
    """Per-folder document counts for `folder_ids`, one query for as many
    folders as `GET /v1/folders` needs (avoids N+1)."""
    if not folder_ids:
        return {}
    rows = await session.execute(
        select(Document.folder_id, func.count())
        .where(Document.folder_id.in_(folder_ids))
        .group_by(Document.folder_id)
    )
    return {folder_id: count for folder_id, count in rows.all() if folder_id is not None}


def _to_out(folder: Folder, document_count: int) -> FolderOut:
    return FolderOut(
        id=folder.id, name=folder.name, created_at=folder.created_at, document_count=document_count
    )


async def _check_name_conflict(
    session: AsyncSession, name: str, *, exclude_id: int | None = None
) -> None:
    """Case-sensitive uniqueness (docs/ingestion.md — the simple rule chosen
    for this feature)."""
    stmt = select(Folder.id).where(Folder.name == name)
    if exclude_id is not None:
        stmt = stmt.where(Folder.id != exclude_id)
    conflict = (await session.execute(stmt)).scalar_one_or_none()
    if conflict is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"a folder named {name!r} already exists",
        )


@router.get("", response_model=list[FolderOut])
async def list_folders(session: AsyncSession = Depends(get_session)) -> list[FolderOut]:
    folders = (await session.execute(select(Folder).order_by(Folder.id))).scalars().all()
    counts = await _document_counts(session, [folder.id for folder in folders])
    return [_to_out(folder, counts.get(folder.id, 0)) for folder in folders]


@router.post("", response_model=FolderOut, status_code=status.HTTP_201_CREATED)
async def create_folder(
    body: FolderIn, session: AsyncSession = Depends(get_session)
) -> FolderOut:
    await _check_name_conflict(session, body.name)

    folder = Folder(name=body.name)
    session.add(folder)
    await session.commit()
    await session.refresh(folder)
    return _to_out(folder, document_count=0)


@router.patch("/{folder_id}", response_model=FolderOut)
async def rename_folder(
    folder_id: int, body: FolderIn, session: AsyncSession = Depends(get_session)
) -> FolderOut:
    folder = await _get_folder_or_404(folder_id, session)
    await _check_name_conflict(session, body.name, exclude_id=folder_id)

    folder.name = body.name
    await session.commit()
    await session.refresh(folder)
    counts = await _document_counts(session, [folder.id])
    return _to_out(folder, counts.get(folder.id, 0))


@router.delete("/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_folder(folder_id: int, session: AsyncSession = Depends(get_session)) -> None:
    """Always allowed (docs/ingestion.md — 文件自動變未分類): `documents.
    folder_id`'s `ON DELETE SET NULL` unfiles every document that was in
    this folder as part of the same delete, never blocking it."""
    folder = await _get_folder_or_404(folder_id, session)
    await session.delete(folder)
    await session.commit()
