"""`backend.ingestion.classification.get_or_create_category` — real-Postgres test.

Hierarchical category dedup (subject/topic) is exactly the kind of logic
.rule flags as needing a real test: getting this wrong means every chunk
classified into an existing subject/topic silently creates a duplicate
`categories` row instead of reusing it.
"""

from sqlalchemy import select

from backend.db.session import AsyncSessionLocal
from backend.ingestion.classification import get_or_create_category
from backend.models.category import Category


async def test_get_or_create_category_creates_once() -> None:
    async with AsyncSessionLocal() as session:
        category = await get_or_create_category(session, "生物", parent_id=None)
        assert category.id is not None
        assert category.name == "生物"
        assert category.parent_id is None


async def test_get_or_create_category_reuses_existing_row_for_same_name_and_parent() -> None:
    async with AsyncSessionLocal() as session:
        first = await get_or_create_category(session, "生物", parent_id=None)
        second = await get_or_create_category(session, "生物", parent_id=None)
        assert first.id == second.id


async def test_get_or_create_category_same_name_different_parent_are_distinct() -> None:
    async with AsyncSessionLocal() as session:
        subject_a = await get_or_create_category(session, "生物", parent_id=None)
        subject_b = await get_or_create_category(session, "地球科學", parent_id=None)

        topic_under_a = await get_or_create_category(session, "光合作用", parent_id=subject_a.id)
        topic_under_b = await get_or_create_category(session, "光合作用", parent_id=subject_b.id)

        assert topic_under_a.id != topic_under_b.id
        assert topic_under_a.parent_id == subject_a.id
        assert topic_under_b.parent_id == subject_b.id


async def test_get_or_create_category_builds_a_two_level_hierarchy() -> None:
    async with AsyncSessionLocal() as session:
        subject = await get_or_create_category(session, "生物", parent_id=None)
        topic = await get_or_create_category(session, "呼吸作用", parent_id=subject.id)

        rows = (
            (await session.execute(select(Category).where(Category.id == topic.id)))
            .scalars()
            .all()
        )
        assert len(rows) == 1
        assert rows[0].parent_id == subject.id
