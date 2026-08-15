"""`GET /v1/assets/{id}` — serve one cropped figure image (docs/ingestion.md 圖表裁切)."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_session
from backend.models.asset import Asset

router = APIRouter(prefix="/assets", tags=["assets"])


@router.get("/{asset_id}")
async def get_asset(asset_id: int, session: AsyncSession = Depends(get_session)) -> FileResponse:
    asset = await session.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="asset not found")

    path = Path(asset.file_path)
    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="asset file missing on disk"
        )

    # Every crop is written as PNG (backend.ingestion.pipeline._crop_figures_and_rewrite).
    return FileResponse(path, media_type="image/png")
