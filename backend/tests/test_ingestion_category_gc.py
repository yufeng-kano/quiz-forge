"""`backend.ingestion.category_gc.gc_unused_categories` (.rule 反偷懶規則 —
job queue/分類 GC 屬高風險邏輯，須有真實 DB 測試；docs/ingestion.md 文件刪除).

Every test drives the function directly against a real Postgres session —
no document/chunk pipeline machinery involved, just the `categories`/
`chunks` rows the predicate actually reads.
"""

from sqlalchemy import select

from backend.db.session import AsyncSessionLocal
from backend.ingestion.category_gc import gc_unused_categories
from backend.ingestion.classification import get_or_create_category
from backend.models.category import Category
from backend.models.chunk import Chunk
from backend.models.document import Document


async def _make_document() -> int:
    async with AsyncSessionLocal() as session:
        document = Document(source_type="upload", title="doc", status="ready")
        session.add(document)
        await session.commit()
        await session.refresh(document)
        return document.id


async def _make_chunk(document_id: int, category_id: int | None, content: str = "內容") -> int:
    async with AsyncSessionLocal() as session:
        chunk = Chunk(document_id=document_id, content=content, category_id=category_id)
        session.add(chunk)
        await session.commit()
        await session.refresh(chunk)
        return chunk.id


async def _category_ids() -> set[int]:
    async with AsyncSessionLocal() as session:
        rows = (await session.execute(select(Category.id))).scalars().all()
        return set(rows)


async def test_orphan_topic_with_no_chunk_reference_is_deleted() -> None:
    async with AsyncSessionLocal() as session:
        subject = await get_or_create_category(session, "生物", parent_id=None)
        topic = await get_or_create_category(session, "光合作用", parent_id=subject.id)
    # No chunk ever references `topic` -- an orphan from the start.

    async with AsyncSessionLocal() as session:
        await gc_unused_categories(session)
        await session.commit()

    remaining = await _category_ids()
    assert topic.id not in remaining
    # The subject has no chunk reference either and, after the topic is
    # gone, no children -- it must go too.
    assert subject.id not in remaining


async def test_topic_referenced_by_a_chunk_survives() -> None:
    document_id = await _make_document()
    async with AsyncSessionLocal() as session:
        subject = await get_or_create_category(session, "生物", parent_id=None)
        topic = await get_or_create_category(session, "光合作用", parent_id=subject.id)
    await _make_chunk(document_id, topic.id)

    async with AsyncSessionLocal() as session:
        await gc_unused_categories(session)
        await session.commit()

    remaining = await _category_ids()
    assert topic.id in remaining
    assert subject.id in remaining


async def test_subject_survives_when_it_still_has_a_referenced_sibling_topic() -> None:
    """Subject 生物 has two topics: 光合作用 (about to become orphaned) and
    呼吸作用 (still referenced). The subject itself must survive because it
    still has a child, even though nothing points at the subject row
    directly."""
    document_id = await _make_document()
    async with AsyncSessionLocal() as session:
        subject = await get_or_create_category(session, "生物", parent_id=None)
        orphan_topic = await get_or_create_category(session, "光合作用", parent_id=subject.id)
        kept_topic = await get_or_create_category(session, "呼吸作用", parent_id=subject.id)
    await _make_chunk(document_id, kept_topic.id)
    # `orphan_topic` intentionally gets no chunk.

    async with AsyncSessionLocal() as session:
        await gc_unused_categories(session)
        await session.commit()

    remaining = await _category_ids()
    assert orphan_topic.id not in remaining
    assert kept_topic.id in remaining
    assert subject.id in remaining


async def test_subject_with_no_children_and_no_direct_chunk_reference_is_deleted() -> None:
    async with AsyncSessionLocal() as session:
        subject = await get_or_create_category(session, "數學", parent_id=None)
    # A childless subject nothing ever chunked directly into.

    async with AsyncSessionLocal() as session:
        await gc_unused_categories(session)
        await session.commit()

    remaining = await _category_ids()
    assert subject.id not in remaining


async def test_subject_directly_referenced_by_a_chunk_survives_even_when_childless() -> None:
    document_id = await _make_document()
    async with AsyncSessionLocal() as session:
        subject = await get_or_create_category(session, "數學", parent_id=None)
    await _make_chunk(document_id, subject.id)

    async with AsyncSessionLocal() as session:
        await gc_unused_categories(session)
        await session.commit()

    remaining = await _category_ids()
    assert subject.id in remaining


async def test_category_shared_across_two_documents_survives_until_both_stop_referencing_it() -> (
    None
):
    doc_a = await _make_document()
    doc_b = await _make_document()
    async with AsyncSessionLocal() as session:
        subject = await get_or_create_category(session, "生物", parent_id=None)
        topic = await get_or_create_category(session, "光合作用", parent_id=subject.id)
    chunk_a = await _make_chunk(doc_a, topic.id, content="doc A 的內容")
    await _make_chunk(doc_b, topic.id, content="doc B 的內容")

    # Simulate "document A deleted": its chunk is gone, but the category is
    # still referenced by document B's chunk.
    async with AsyncSessionLocal() as session:
        chunk = await session.get(Chunk, chunk_a)
        assert chunk is not None
        await session.delete(chunk)
        await session.flush()
        await gc_unused_categories(session)
        await session.commit()

    remaining = await _category_ids()
    assert topic.id in remaining
    assert subject.id in remaining

    # Now document B's chunk goes too -- nothing references the category
    # anymore, GC removes it.
    async with AsyncSessionLocal() as session:
        remaining_chunks = (
            (await session.execute(select(Chunk).where(Chunk.document_id == doc_b)))
            .scalars()
            .all()
        )
        for chunk in remaining_chunks:
            await session.delete(chunk)
        await session.flush()
        await gc_unused_categories(session)
        await session.commit()

    remaining = await _category_ids()
    assert topic.id not in remaining
    assert subject.id not in remaining


async def test_unrelated_referenced_category_is_untouched() -> None:
    """A sanity check that GC doesn't over-delete: an entirely separate,
    still-referenced subject/topic pair must be left alone by a GC run
    triggered by cleanup of a different category tree."""
    document_id = await _make_document()
    async with AsyncSessionLocal() as session:
        kept_subject = await get_or_create_category(session, "化學", parent_id=None)
        kept_topic = await get_or_create_category(session, "酸鹼反應", parent_id=kept_subject.id)
        orphan_subject = await get_or_create_category(session, "地理", parent_id=None)
    await _make_chunk(document_id, kept_topic.id)
    # `orphan_subject` has no children and no chunk -- should be collected.

    async with AsyncSessionLocal() as session:
        await gc_unused_categories(session)
        await session.commit()

    remaining = await _category_ids()
    assert kept_subject.id in remaining
    assert kept_topic.id in remaining
    assert orphan_subject.id not in remaining
