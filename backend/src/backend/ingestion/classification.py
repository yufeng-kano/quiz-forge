"""Chunk classification (subject/topic/difficulty/tags) and category get-or-create.

docs/ingestion.md — "每個 chunk 由 TEXT_MODEL 依分類 schema 標註：科目／主題／
難度／標籤（categories 支援階層)". `subject` and `topic` map to hierarchical
`categories` rows (topic's parent = subject), get-or-create so re-classifying
another chunk into the same subject/topic reuses the same row instead of
duplicating it.
"""

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.ingestion.prompts import CLASSIFICATION_PROMPT_TEMPLATE
from backend.llm.client import LLMClient
from backend.models.category import Category


class ChunkClassification(BaseModel):
    """The exact `response_format: json_schema` shape for one chunk's classification call."""

    subject: str
    topic: str
    difficulty: str
    tags: list[str]


async def classify_chunk(llm: LLMClient, content: str) -> ChunkClassification:
    """One `TEXT_MODEL` json_schema call labelling `content`'s subject/topic/difficulty/tags."""
    return await llm.chat(
        messages=[
            {
                "role": "user",
                "content": CLASSIFICATION_PROMPT_TEMPLATE.format(content=content),
            }
        ],
        response_model=ChunkClassification,
        purpose="classify_chunk",
    )


async def get_or_create_category(
    session: AsyncSession, name: str, parent_id: int | None
) -> Category:
    """Return the `categories` row for `(name, parent_id)`, creating it if absent."""
    parent_condition = (
        Category.parent_id.is_(None) if parent_id is None else Category.parent_id == parent_id
    )
    existing = (
        await session.execute(
            select(Category).where(Category.name == name, parent_condition)
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    category = Category(name=name, parent_id=parent_id)
    session.add(category)
    await session.commit()
    await session.refresh(category)
    return category
