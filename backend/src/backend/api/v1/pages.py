"""`POST /v1/pages/{id}/retry` — minimal-unit page retry (.rule 使用者體驗規則:
任務失敗必須可以最小單位重試；docs/ingestion.md 單頁失敗單頁重試).

Unlike `POST /v1/jobs/{id}/retry` (which resets an existing failed job back
to `pending`), a page retry always enqueues a brand new `parse_page` job:
the `parse_document` job that originally parsed this page reaches `done`
even when individual pages failed (see `backend.ingestion.pipeline`), so
there is no failed job left to reset.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_session
from backend.models.job import Job
from backend.models.page import Page
from backend.schemas.job import JobOut

router = APIRouter(prefix="/pages", tags=["pages"])


@router.post("/{page_id}/retry", response_model=JobOut, status_code=status.HTTP_201_CREATED)
async def retry_page(page_id: int, session: AsyncSession = Depends(get_session)) -> Job:
    page = await session.get(Page, page_id)
    if page is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="page not found")
    if page.status not in ("ready", "failed"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"page {page_id} is {page.status!r}; can only retry a ready/failed page",
        )

    job = Job(kind="parse_page", payload={"page_id": page.id})
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job
