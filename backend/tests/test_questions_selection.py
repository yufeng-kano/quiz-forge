"""`backend.questions.selection` — material selection for question generation
(.rule 反偷懶規則: comparison pairing band selection 屬高風險邏輯，須對真實
Postgres 測試).

`find_comparison_candidate_pairs` is exercised against a real pgvector
column with seeded embeddings whose exact cosine similarity is controlled by
construction (unit vectors at a chosen angle apart: similarity == cos(angle)),
so the expected in-band/out-of-band set is known ahead of time, not just
"non-empty". `pick_comparison_pairs`/`select_single_chunk_units` (the pure
selection algorithms) are covered with plain unit tests.
"""

import math

from backend.core.config import get_settings
from backend.db.session import AsyncSessionLocal
from backend.models.category import Category
from backend.models.chunk import Chunk
from backend.models.document import Document
from backend.questions.selection import (
    GenerationUnit,
    find_comparison_candidate_pairs,
    find_eligible_chunks,
    pick_comparison_pairs,
    select_single_chunk_units,
    select_units,
)


def _unit_vector(angle_degrees: float, dim: int) -> list[float]:
    """A unit vector in the plane spanned by the first two axes, `angle_degrees`
    around from the reference vector (1, 0, 0, ...) — so
    `cosine_similarity(_unit_vector(0, dim), _unit_vector(theta, dim)) == cos(theta)`
    exactly, giving each seeded chunk a known, exact similarity to the others."""
    radians = math.radians(angle_degrees)
    vector = [0.0] * dim
    vector[0] = math.cos(radians)
    vector[1] = math.sin(radians)
    return vector


async def _make_document() -> int:
    async with AsyncSessionLocal() as session:
        document = Document(source_type="upload", title="doc", status="ready")
        session.add(document)
        await session.commit()
        await session.refresh(document)
        return document.id


async def _make_category(name: str = "分類") -> int:
    async with AsyncSessionLocal() as session:
        category = Category(name=name, parent_id=None)
        session.add(category)
        await session.commit()
        await session.refresh(category)
        return category.id


async def _make_chunk(
    *,
    document_id: int,
    category_id: int | None,
    content: str,
    embedding: list[float] | None,
) -> int:
    async with AsyncSessionLocal() as session:
        chunk = Chunk(
            document_id=document_id, content=content, category_id=category_id, embedding=embedding
        )
        session.add(chunk)
        await session.commit()
        await session.refresh(chunk)
        return chunk.id


# ---------------------------------------------------------------------------
# find_comparison_candidate_pairs — real Postgres, seeded embeddings
# ---------------------------------------------------------------------------


async def test_find_comparison_candidate_pairs_returns_exactly_the_in_band_set() -> None:
    dim = get_settings().embedding_dim
    document_id = await _make_document()
    category_id = await _make_category()

    # A=0°, B=50° (A-B similarity = cos50 ≈ 0.643, inside [0.35, 0.75]),
    # C=5° (A-C ≈ cos5 ≈ 0.996, above max -- near-duplicate),
    # D=89° (A-D ≈ cos89 ≈ 0.017, below min -- unrelated).
    a = await _make_chunk(
        document_id=document_id,
        category_id=category_id,
        content="A",
        embedding=_unit_vector(0, dim),
    )
    b = await _make_chunk(
        document_id=document_id,
        category_id=category_id,
        content="B",
        embedding=_unit_vector(50, dim),
    )
    c = await _make_chunk(
        document_id=document_id,
        category_id=category_id,
        content="C",
        embedding=_unit_vector(5, dim),
    )
    d = await _make_chunk(
        document_id=document_id,
        category_id=category_id,
        content="D",
        embedding=_unit_vector(89, dim),
    )

    async with AsyncSessionLocal() as session:
        candidates = await find_comparison_candidate_pairs(
            session,
            document_ids=None,
            category_ids=None,
            similarity_min=0.35,
            similarity_max=0.75,
        )

    pairs_found = {frozenset((row[0], row[1])) for row in candidates}
    # every returned similarity must itself be inside the requested band.
    for _a, _b, similarity in candidates:
        assert 0.35 <= similarity <= 0.75

    assert frozenset((a, b)) in pairs_found
    assert frozenset((a, c)) not in pairs_found
    assert frozenset((a, d)) not in pairs_found


async def test_find_comparison_candidate_pairs_excludes_different_categories() -> None:
    dim = get_settings().embedding_dim
    document_id = await _make_document()
    category_1 = await _make_category("分類一")
    category_2 = await _make_category("分類二")

    a = await _make_chunk(
        document_id=document_id, category_id=category_1, content="A", embedding=_unit_vector(0, dim)
    )
    b_other_category = await _make_chunk(
        document_id=document_id,
        category_id=category_2,
        content="B-other-category",
        embedding=_unit_vector(50, dim),  # same similarity to A as the in-band case above
    )

    async with AsyncSessionLocal() as session:
        candidates = await find_comparison_candidate_pairs(
            session,
            document_ids=None,
            category_ids=None,
            similarity_min=0.35,
            similarity_max=0.75,
        )

    pairs_found = {frozenset((row[0], row[1])) for row in candidates}
    assert frozenset((a, b_other_category)) not in pairs_found


async def test_find_comparison_candidate_pairs_excludes_unembedded_chunks() -> None:
    dim = get_settings().embedding_dim
    document_id = await _make_document()
    category_id = await _make_category()

    a = await _make_chunk(
        document_id=document_id,
        category_id=category_id,
        content="A",
        embedding=_unit_vector(0, dim),
    )
    unembedded = await _make_chunk(
        document_id=document_id, category_id=category_id, content="not embedded yet", embedding=None
    )

    async with AsyncSessionLocal() as session:
        candidates = await find_comparison_candidate_pairs(
            session,
            document_ids=None,
            category_ids=None,
            similarity_min=0.0,
            similarity_max=1.0,
        )

    pairs_found = {frozenset((row[0], row[1])) for row in candidates}
    assert not any(unembedded in pair for pair in pairs_found)
    assert a is not None  # sanity: a was actually created


async def test_find_comparison_candidate_pairs_respects_document_scope() -> None:
    dim = get_settings().embedding_dim
    document_1 = await _make_document()
    document_2 = await _make_document()
    category_id = await _make_category()

    a = await _make_chunk(
        document_id=document_1, category_id=category_id, content="A", embedding=_unit_vector(0, dim)
    )
    b_other_document = await _make_chunk(
        document_id=document_2,
        category_id=category_id,
        content="B",
        embedding=_unit_vector(50, dim),
    )

    async with AsyncSessionLocal() as session:
        scoped_candidates = await find_comparison_candidate_pairs(
            session,
            document_ids=[document_1],
            category_ids=None,
            similarity_min=0.35,
            similarity_max=0.75,
        )
        unscoped_candidates = await find_comparison_candidate_pairs(
            session,
            document_ids=None,
            category_ids=None,
            similarity_min=0.35,
            similarity_max=0.75,
        )

    scoped_pairs = {frozenset((row[0], row[1])) for row in scoped_candidates}
    unscoped_pairs = {frozenset((row[0], row[1])) for row in unscoped_candidates}
    assert frozenset((a, b_other_document)) not in scoped_pairs
    assert frozenset((a, b_other_document)) in unscoped_pairs


# ---------------------------------------------------------------------------
# pick_comparison_pairs — pure selection algorithm
# ---------------------------------------------------------------------------


def test_pick_comparison_pairs_prefers_chunk_disjoint_pairs() -> None:
    # 6 chunks, 3 disjoint pairs available -- must use all 6 distinct chunks.
    candidates = [(1, 2, 0.5), (3, 4, 0.5), (5, 6, 0.5)]
    pairs = pick_comparison_pairs(candidates, count=3)
    assert len(pairs) == 3
    used_chunks = [chunk_id for pair in pairs for chunk_id in pair]
    assert len(used_chunks) == len(set(used_chunks)), "all 6 chunks should be used exactly once"


def test_pick_comparison_pairs_never_returns_more_than_available_when_scarce() -> None:
    # Only one valid pair exists at all -- requesting 5 must not fabricate
    # duplicates of it (.rule 反偷懶規則: 不得假完成).
    candidates = [(1, 2, 0.5)]
    pairs = pick_comparison_pairs(candidates, count=5)
    assert pairs == [(1, 2)]


def test_pick_comparison_pairs_reuses_a_chunk_only_once_disjoint_options_run_out() -> None:
    # 3 chunks -> only 1 disjoint pair possible, but 3 distinct pairs total.
    candidates = [(1, 2, 0.5), (1, 3, 0.5), (2, 3, 0.5)]
    pairs = pick_comparison_pairs(candidates, count=3)
    assert len(pairs) == 3
    assert len(set(pairs)) == len({frozenset(p) for p in pairs}) == 3, "no exact pair repeats"


def test_pick_comparison_pairs_empty_candidates_returns_empty() -> None:
    assert pick_comparison_pairs([], count=3) == []


# ---------------------------------------------------------------------------
# select_single_chunk_units — pure selection algorithm
# ---------------------------------------------------------------------------


def _local_chunk(chunk_id: int, content: str) -> Chunk:
    """An unpersisted `Chunk` instance — `select_single_chunk_units` only ever
    reads `.id`/`.content`, so this pure-function test never needs a DB
    round trip; `id` is normally DB-assigned but can be set directly on an
    unflushed ORM instance."""
    chunk = Chunk(content=content)
    chunk.id = chunk_id
    return chunk


def test_select_single_chunk_units_no_repeats_when_count_within_pool() -> None:
    chunks = [_local_chunk(i, f"content-{i}") for i in range(5)]
    units = select_single_chunk_units(chunks, count=5)
    ids = [unit.chunk_ids[0] for unit in units]
    assert sorted(ids) == [0, 1, 2, 3, 4]


def test_select_single_chunk_units_cycles_when_count_exceeds_pool() -> None:
    chunks = [_local_chunk(i, f"content-{i}") for i in range(3)]
    units = select_single_chunk_units(chunks, count=7)
    assert len(units) == 7
    ids = [unit.chunk_ids[0] for unit in units]
    # every chunk used at least twice (7 draws over a pool of 3 -> min 2 each)
    for chunk_id in (0, 1, 2):
        assert ids.count(chunk_id) >= 2


def test_select_single_chunk_units_empty_pool_returns_empty() -> None:
    assert select_single_chunk_units([], count=3) == []


# ---------------------------------------------------------------------------
# select_units — the async orchestrator, real Postgres
# ---------------------------------------------------------------------------


async def test_select_units_single_chunk_type_returns_scoped_chunks() -> None:
    document_id = await _make_document()
    category_id = await _make_category()
    await _make_chunk(
        document_id=document_id, category_id=category_id, content="第一段", embedding=None
    )
    await _make_chunk(
        document_id=document_id, category_id=category_id, content="第二段", embedding=None
    )

    async with AsyncSessionLocal() as session:
        units = await select_units(
            session,
            question_type="single_choice",
            document_ids=[document_id],
            category_ids=None,
            count=2,
            settings=get_settings(),
        )

    assert len(units) == 2
    assert all(isinstance(unit, GenerationUnit) for unit in units)
    assert all(len(unit.chunk_ids) == 1 for unit in units)
    contents = {unit.contents[0] for unit in units}
    assert contents == {"第一段", "第二段"}


async def test_select_units_comparison_type_returns_paired_chunks_with_content() -> None:
    dim = get_settings().embedding_dim
    document_id = await _make_document()
    category_id = await _make_category()
    await _make_chunk(
        document_id=document_id,
        category_id=category_id,
        content="光合作用內容",
        embedding=_unit_vector(0, dim),
    )
    await _make_chunk(
        document_id=document_id,
        category_id=category_id,
        content="呼吸作用內容",
        embedding=_unit_vector(50, dim),
    )

    settings = get_settings()
    async with AsyncSessionLocal() as session:
        units = await select_units(
            session,
            question_type="comparison",
            document_ids=[document_id],
            category_ids=None,
            count=1,
            settings=settings,
        )

    assert len(units) == 1
    unit = units[0]
    assert len(unit.chunk_ids) == 2
    assert set(unit.contents) == {"光合作用內容", "呼吸作用內容"}


async def test_select_units_returns_empty_when_scope_has_no_chunks() -> None:
    document_id = await _make_document()
    async with AsyncSessionLocal() as session:
        units = await select_units(
            session,
            question_type="single_choice",
            document_ids=[document_id],
            category_ids=None,
            count=3,
            settings=get_settings(),
        )
    assert units == []


async def test_find_eligible_chunks_respects_category_scope() -> None:
    document_id = await _make_document()
    category_1 = await _make_category("分類一")
    category_2 = await _make_category("分類二")
    in_scope = await _make_chunk(
        document_id=document_id, category_id=category_1, content="in", embedding=None
    )
    await _make_chunk(
        document_id=document_id, category_id=category_2, content="out", embedding=None
    )

    async with AsyncSessionLocal() as session:
        chunks = await find_eligible_chunks(
            session, document_ids=None, category_ids=[category_1]
        )

    assert [chunk.id for chunk in chunks] == [in_scope]
