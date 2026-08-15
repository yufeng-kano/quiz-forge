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

from backend.core.config import Settings
from backend.ingestion.prompts import build_classification_prompt
from backend.llm.client import LLMClient
from backend.models.category import Category


class ChunkClassification(BaseModel):
    """The exact `response_format: json_schema` shape for one chunk's classification call."""

    subject: str
    topic: str
    difficulty: str
    tags: list[str]


async def load_existing_categories(
    session: AsyncSession, *, subjects_limit: int, topics_per_subject_limit: int
) -> list[tuple[str, list[str]]]:
    """`[(subject_name, [existing_topic_name, ...]), ...]` for the classification
    prompt (docs/ingestion.md — 分類 prompt 必須帶入既有科目清單與該科目下既有
    主題). Capped at `subjects_limit` subjects (oldest first) and
    `topics_per_subject_limit` topics per subject, so the prompt stays
    bounded as the category tree grows across a long-running instance."""
    subjects = (
        (
            await session.execute(
                select(Category)
                .where(Category.parent_id.is_(None))
                .order_by(Category.id)
                .limit(subjects_limit)
            )
        )
        .scalars()
        .all()
    )
    if not subjects:
        return []

    subject_ids = [subject.id for subject in subjects]
    topics = (
        (
            await session.execute(
                select(Category).where(Category.parent_id.in_(subject_ids)).order_by(Category.id)
            )
        )
        .scalars()
        .all()
    )
    topics_by_subject: dict[int, list[str]] = {subject_id: [] for subject_id in subject_ids}
    for topic in topics:
        assert topic.parent_id is not None  # guaranteed by the `.in_(subject_ids)` filter above
        topics_by_subject[topic.parent_id].append(topic.name)

    return [
        (subject.name, topics_by_subject[subject.id][:topics_per_subject_limit])
        for subject in subjects
    ]


async def classify_chunk(
    llm: LLMClient, session: AsyncSession, content: str, settings: Settings
) -> ChunkClassification:
    """One `TEXT_MODEL` json_schema call labelling `content`'s subject/topic/difficulty/tags.

    The prompt includes the current subject/topic tree (capped per
    `settings`) so the model reuses an existing name instead of fragmenting
    synonymous subjects across chunks/documents (docs/ingestion.md)."""
    existing = await load_existing_categories(
        session,
        subjects_limit=settings.classification_existing_subjects_limit,
        topics_per_subject_limit=settings.classification_existing_topics_per_subject_limit,
    )
    return await llm.chat(
        messages=[
            {
                "role": "user",
                "content": build_classification_prompt(content, existing),
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
