"""`GET /v1/categories` — every category, flat (docs/data-model.md 階層分類).

Returns every row with its `parent_id` so a client can build the
subject/topic tree itself (e.g. render 「生物 › 光合作用」 by walking a topic
row up to its subject row) — used by the generate page's scope picker and by
the documents page to resolve a chunk's full category path."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_session
from backend.models.category import Category
from backend.schemas.document import CategoryOut

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=list[CategoryOut])
async def list_categories(session: AsyncSession = Depends(get_session)) -> list[CategoryOut]:
    categories = (await session.execute(select(Category).order_by(Category.id))).scalars().all()
    return [CategoryOut.model_validate(category) for category in categories]
