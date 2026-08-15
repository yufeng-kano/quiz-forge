"""Material selection for question generation (docs/question-bank.md 出題流程).

- Non-`comparison` types: one chunk per question, sampled without
  replacement from the scoped chunk pool where possible — repeats only
  happen once every chunk has already been used once (.rule 反偷懶規則:
  避免部分處理／不真實抽樣，同時 count 超過池子大小時仍要出完整份數).
- `comparison`: chunk *pairs* within the same category, restricted to a
  "related but not identical" cosine-similarity band
  (`COMPARISON_SIMILARITY_MIN`/`MAX` settings — never hardcoded), picked
  without reusing the exact same pair twice where possible.

Both scoring paths funnel through `select_units`, which the `generate_questions`
job handler calls without needing to know whether its type pairs chunks or not.
"""

import random
from dataclasses import dataclass

from sqlalchemy import ColumnElement, ScalarSelect, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute, aliased

from backend.core.config import Settings
from backend.models.category import Category
from backend.models.chunk import Chunk


@dataclass(frozen=True)
class GenerationUnit:
    """One question's worth of source material: the chunk id(s) feeding the
    LLM call, in the order their content should appear in the prompt."""

    chunk_ids: list[int]
    contents: list[str]


def _scope_conditions(
    entity: type[Chunk], document_ids: list[int] | None, category_ids: list[int] | None
) -> list[ColumnElement[bool]]:
    conditions: list[ColumnElement[bool]] = []
    if document_ids:
        conditions.append(entity.document_id.in_(document_ids))
    if category_ids:
        conditions.append(entity.category_id.in_(category_ids))
    return conditions


async def find_eligible_chunks(
    session: AsyncSession,
    *,
    document_ids: list[int] | None,
    category_ids: list[int] | None,
) -> list[Chunk]:
    """All chunks matching scope, oldest-id-first — the pool every
    non-comparison type samples from."""
    stmt = select(Chunk).where(*_scope_conditions(Chunk, document_ids, category_ids))
    stmt = stmt.order_by(Chunk.id)
    return list((await session.execute(stmt)).scalars().all())


def select_single_chunk_units(chunks: list[Chunk], count: int) -> list[GenerationUnit]:
    """Pick `count` chunks, one per question. A single shuffled pass through
    `chunks` never repeats one; once that pass is exhausted (count > pool
    size), a fresh shuffled pass starts over so every chunk gets used before
    any chunk gets used twice."""
    if not chunks or count <= 0:
        return []
    units: list[GenerationUnit] = []
    while len(units) < count:
        pool = list(chunks)
        random.shuffle(pool)
        for chunk in pool:
            if len(units) >= count:
                break
            units.append(GenerationUnit(chunk_ids=[chunk.id], contents=[chunk.content]))
    return units


async def find_comparison_candidate_pairs(
    session: AsyncSession,
    *,
    document_ids: list[int] | None,
    category_ids: list[int] | None,
    similarity_min: float,
    similarity_max: float,
) -> list[tuple[int, int, float]]:
    """`(chunk_a_id, chunk_b_id, similarity)` triples for every both-embedded
    chunk pair under the same *subject* whose cosine similarity falls in
    `[similarity_min, similarity_max]` — "related but not identical"
    (docs/question-bank.md 比較題 素材選取).

    "同分類" is read at the subject level, not the exact topic: ingestion
    classifies each chunk into a two-level subject/topic hierarchy
    (`backend.ingestion.classification` — topic's `parent_id` is its
    subject), so two chunks worth comparing are typically two *different*
    but related topics under one subject (e.g. 光合作用 vs 細胞呼吸作用 under
    生物) rather than two chunks of the identical topic. A category with no
    parent already *is* a subject, so `COALESCE(parent_id, id)` gives every
    chunk's subject id regardless of which level it was classified at.
    """
    a = aliased(Chunk)
    b = aliased(Chunk)
    similarity = (1 - a.embedding.cosine_distance(b.embedding)).label("similarity")
    subject_a = _subject_id_subquery(a.category_id)
    subject_b = _subject_id_subquery(b.category_id)

    conditions: list[ColumnElement[bool]] = [
        a.id < b.id,
        subject_a == subject_b,
        a.embedding.is_not(None),
        b.embedding.is_not(None),
        similarity >= similarity_min,
        similarity <= similarity_max,
    ]
    conditions.extend(_scope_conditions(a, document_ids, category_ids))
    conditions.extend(_scope_conditions(b, document_ids, category_ids))

    stmt = select(a.id, b.id, similarity).where(*conditions)
    rows = (await session.execute(stmt)).all()
    return [(row[0], row[1], row[2]) for row in rows]


def _subject_id_subquery(
    category_id_column: InstrumentedAttribute[int | None],
) -> ScalarSelect[int]:
    """A correlated scalar subquery resolving `category_id_column` to its
    subject id — `COALESCE(parent_id, id)`, since a category with no parent
    already *is* a subject. A plain correlated subquery (rather than a
    second join) sidesteps FROM-clause ordering entirely: each side (`a`,
    `b`) gets its own independent subquery, so there's no join-order
    constraint between the two chunk aliases and their respective category
    lookups."""
    return (
        select(func.coalesce(Category.parent_id, Category.id))
        .where(Category.id == category_id_column)
        .scalar_subquery()
    )


def pick_comparison_pairs(
    candidates: list[tuple[int, int, float]], count: int
) -> list[tuple[int, int]]:
    """Greedily choose up to `count` pairs from `candidates`, preferring pairs
    that share no chunk with an already-selected pair. Only once every
    chunk-disjoint option is exhausted does a chunk get reused across two
    pairs — the exact same pair is never selected twice."""
    if not candidates or count <= 0:
        return []
    shuffled = list(candidates)
    random.shuffle(shuffled)

    selected: list[tuple[int, int]] = []
    used_chunks: set[int] = set()
    leftover: list[tuple[int, int]] = []
    for chunk_a_id, chunk_b_id, _similarity in shuffled:
        if chunk_a_id in used_chunks or chunk_b_id in used_chunks:
            leftover.append((chunk_a_id, chunk_b_id))
            continue
        selected.append((chunk_a_id, chunk_b_id))
        used_chunks.add(chunk_a_id)
        used_chunks.add(chunk_b_id)

    if len(selected) < count:
        selected_pairs = {frozenset(pair) for pair in selected}
        for chunk_a_id, chunk_b_id in leftover:
            if len(selected) >= count:
                break
            key = frozenset((chunk_a_id, chunk_b_id))
            if key in selected_pairs:
                continue
            selected.append((chunk_a_id, chunk_b_id))
            selected_pairs.add(key)

    return selected[:count]


async def _load_contents(session: AsyncSession, chunk_ids: list[int]) -> dict[int, str]:
    rows = (
        await session.execute(select(Chunk.id, Chunk.content).where(Chunk.id.in_(chunk_ids)))
    ).all()
    return {row[0]: row[1] for row in rows}


async def select_units(
    session: AsyncSession,
    *,
    question_type: str,
    document_ids: list[int] | None,
    category_ids: list[int] | None,
    count: int,
    settings: Settings,
) -> list[GenerationUnit]:
    """The single entrypoint `generate_questions` calls: `count` units of
    source material for `question_type`, whatever its selection strategy is.

    May return fewer than `count` units when the scope genuinely doesn't
    have that much eligible material (an empty scope, or too few same-
    category embedded chunks/pairs for `comparison`) — the caller decides
    what that means for the job (docs/question-bank.md — 一題失敗不影響其他題).
    """
    if question_type == "comparison":
        candidates = await find_comparison_candidate_pairs(
            session,
            document_ids=document_ids,
            category_ids=category_ids,
            similarity_min=settings.comparison_similarity_min,
            similarity_max=settings.comparison_similarity_max,
        )
        pairs = pick_comparison_pairs(candidates, count)
        if not pairs:
            return []
        chunk_ids = sorted({chunk_id for pair in pairs for chunk_id in pair})
        contents = await _load_contents(session, chunk_ids)
        return [
            GenerationUnit(
                chunk_ids=[chunk_a_id, chunk_b_id],
                contents=[contents[chunk_a_id], contents[chunk_b_id]],
            )
            for chunk_a_id, chunk_b_id in pairs
        ]

    chunks = await find_eligible_chunks(
        session, document_ids=document_ids, category_ids=category_ids
    )
    return select_single_chunk_units(chunks, count)
