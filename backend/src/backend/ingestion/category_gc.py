"""Category garbage collection (docs/ingestion.md 文件刪除) — deletes
`categories` rows no longer referenced by any chunk once a document's
chunks are gone.

Two callers share this: `DELETE /v1/documents/{id}` (after the cascade
delete removes the document's chunks) and the chunk-phase rerun in
`backend.ingestion.pipeline._run_chunk_phase` (both the retry-from-scratch
path inside `parse_document` and `rechunk_document` delete the document's
old chunks and reclassify from scratch, which can leave the old
classification's categories — e.g. a renamed topic — unreferenced too;
.rule 反偷懶規則 不得重複核心邏輯).

Two-phase delete, in order:
1. Topic-level categories (`parent_id IS NOT NULL`) no longer referenced by
   any chunk.
2. Subject-level categories (`parent_id IS NULL`) that, after step 1, have
   no remaining child category AND are not directly referenced by any
   chunk either.

Categories still referenced by another document's chunks are left alone —
the predicate above is purely "no chunk references (and no children for
subjects)", so a shared subject/topic naturally survives as long as at
least one chunk anywhere still points at it.

Caller owns the transaction: this function only `flush`es between the two
phases (so phase 2's "no children" check sees phase 1's deletes) and never
commits — commit once, alongside whatever else the caller's transaction
did.
"""

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.category import Category
from backend.models.chunk import Chunk


async def gc_unused_categories(session: AsyncSession) -> None:
    """Delete orphaned topic categories, then orphaned subject categories."""
    referenced_category_ids = select(Chunk.category_id).where(Chunk.category_id.is_not(None))

    orphan_topic_ids = list(
        (
            await session.execute(
                select(Category.id)
                .where(Category.parent_id.is_not(None))
                .where(Category.id.notin_(referenced_category_ids))
            )
        )
        .scalars()
        .all()
    )
    if orphan_topic_ids:
        await session.execute(delete(Category).where(Category.id.in_(orphan_topic_ids)))
        await session.flush()

    child_subject_ids = select(Category.parent_id).where(Category.parent_id.is_not(None))
    orphan_subject_ids = list(
        (
            await session.execute(
                select(Category.id)
                .where(Category.parent_id.is_(None))
                .where(Category.id.notin_(referenced_category_ids))
                .where(Category.id.notin_(child_subject_ids))
            )
        )
        .scalars()
        .all()
    )
    if orphan_subject_ids:
        await session.execute(delete(Category).where(Category.id.in_(orphan_subject_ids)))
        await session.flush()
