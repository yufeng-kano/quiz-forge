"""`/v1/categories` — every category, flat (docs/data-model.md 階層分類);
rename and guarded delete (docs/question-bank.md `PATCH .../{id}` 改名、
`DELETE .../{id}`（有 chunk 引用或子分類時 409）).

`GET` returns every row with its `parent_id` so a client can build the
subject/topic tree itself (e.g. render 「生物 › 光合作用」 by walking a topic
row up to its subject row) — used by the generate page's scope picker and by
the documents page to resolve a chunk's full category path."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_session
from backend.models.category import Category
from backend.models.chunk import Chunk
from backend.schemas.document import CategoryOut, CategoryPatchIn

router = APIRouter(prefix="/categories", tags=["categories"])


async def _get_category_or_404(category_id: int, session: AsyncSession) -> Category:
    category = await session.get(Category, category_id)
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="category not found")
    return category


@router.get("", response_model=list[CategoryOut])
async def list_categories(session: AsyncSession = Depends(get_session)) -> list[CategoryOut]:
    categories = (await session.execute(select(Category).order_by(Category.id))).scalars().all()
    return [CategoryOut.model_validate(category) for category in categories]


@router.patch("/{category_id}", response_model=CategoryOut)
async def rename_category(
    category_id: int, body: CategoryPatchIn, session: AsyncSession = Depends(get_session)
) -> CategoryOut:
    category = await _get_category_or_404(category_id, session)

    sibling_filter = (
        Category.parent_id.is_(None)
        if category.parent_id is None
        else Category.parent_id == category.parent_id
    )
    conflict = (
        await session.execute(
            select(Category.id).where(
                sibling_filter, Category.name == body.name, Category.id != category_id
            )
        )
    ).scalar_one_or_none()
    if conflict is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"a sibling category named {body.name!r} already exists",
        )

    category.name = body.name
    await session.commit()
    await session.refresh(category)
    return CategoryOut.model_validate(category)


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category_id: int, session: AsyncSession = Depends(get_session)
) -> None:
    """Only when nothing references this category (docs/question-bank.md 有
    chunk 引用或子分類時 409) — deleting it otherwise would either silently
    orphan chunks or silently delete a used subject/topic node."""
    category = await _get_category_or_404(category_id, session)

    chunk_count = (
        await session.execute(
            select(func.count()).select_from(Chunk).where(Chunk.category_id == category_id)
        )
    ).scalar_one()
    if chunk_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"category {category_id} is referenced by {chunk_count} chunk(s)",
        )

    child_count = (
        await session.execute(
            select(func.count()).select_from(Category).where(Category.parent_id == category_id)
        )
    ).scalar_one()
    if child_count > 0:
        noun = "category" if child_count == 1 else "categories"
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"category {category_id} has {child_count} child {noun}",
        )

    await session.delete(category)
    await session.commit()
