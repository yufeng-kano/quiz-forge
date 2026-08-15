"""`/v1/categories` through the real HTTP app: `GET` (list), `PATCH`
(rename, F4), `DELETE` (guarded, F4)."""

from fastapi.testclient import TestClient

from backend.db.session import AsyncSessionLocal
from backend.models.category import Category
from backend.models.chunk import Chunk
from backend.models.document import Document


async def _make_category(name: str, parent_id: int | None = None) -> int:
    async with AsyncSessionLocal() as session:
        category = Category(name=name, parent_id=parent_id)
        session.add(category)
        await session.commit()
        await session.refresh(category)
        return category.id


async def _make_document() -> int:
    async with AsyncSessionLocal() as session:
        document = Document(source_type="upload", title="doc", status="ready")
        session.add(document)
        await session.commit()
        await session.refresh(document)
        return document.id


async def _make_chunk(document_id: int, category_id: int | None) -> int:
    async with AsyncSessionLocal() as session:
        chunk = Chunk(document_id=document_id, content="內容", category_id=category_id)
        session.add(chunk)
        await session.commit()
        await session.refresh(chunk)
        return chunk.id


async def test_list_categories_returns_flat_list_with_parent_ids(client: TestClient) -> None:
    async with AsyncSessionLocal() as session:
        subject = Category(name="生物", parent_id=None)
        session.add(subject)
        await session.commit()
        await session.refresh(subject)

        topic = Category(name="光合作用", parent_id=subject.id)
        session.add(topic)
        await session.commit()
        await session.refresh(topic)

    response = client.get("/v1/categories")

    assert response.status_code == 200
    by_id = {row["id"]: row for row in response.json()}
    assert by_id[subject.id] == {"id": subject.id, "name": "生物", "parent_id": None}
    assert by_id[topic.id] == {"id": topic.id, "name": "光合作用", "parent_id": subject.id}


def test_list_categories_empty_when_none_exist(client: TestClient) -> None:
    response = client.get("/v1/categories")
    assert response.status_code == 200
    assert response.json() == []


# ---------------------------------------------------------------------------
# PATCH /v1/categories/{id} -- rename (F4)
# ---------------------------------------------------------------------------


async def test_rename_category_updates_name(client: TestClient) -> None:
    category_id = await _make_category("生物")

    response = client.patch(f"/v1/categories/{category_id}", json={"name": "生物科"})

    assert response.status_code == 200
    assert response.json() == {"id": category_id, "name": "生物科", "parent_id": None}


async def test_rename_category_strips_whitespace(client: TestClient) -> None:
    category_id = await _make_category("生物")

    response = client.patch(f"/v1/categories/{category_id}", json={"name": "  生物科  "})

    assert response.status_code == 200
    assert response.json()["name"] == "生物科"


def test_rename_category_rejects_blank_name(client: TestClient) -> None:
    response = client.patch("/v1/categories/1", json={"name": "   "})
    assert response.status_code == 422


async def test_rename_category_409_on_sibling_name_conflict(client: TestClient) -> None:
    subject_id = await _make_category("生物")
    await _make_category("光合作用", parent_id=subject_id)
    topic_b_id = await _make_category("呼吸作用", parent_id=subject_id)

    response = client.patch(f"/v1/categories/{topic_b_id}", json={"name": "光合作用"})

    assert response.status_code == 409


async def test_rename_category_allows_same_name_across_different_parents(
    client: TestClient,
) -> None:
    subject_a = await _make_category("生物")
    subject_b = await _make_category("化學")
    topic_id = await _make_category("光合作用", parent_id=subject_b)

    # renaming to a name already used under a *different* parent is fine --
    # uniqueness is only enforced among siblings.
    response = client.patch(f"/v1/categories/{topic_id}", json={"name": "生物"})
    assert response.status_code == 200
    assert subject_a  # keep the fixture referenced


async def test_rename_category_409_on_conflict_among_root_siblings(client: TestClient) -> None:
    await _make_category("生物")
    chemistry_id = await _make_category("化學")

    response = client.patch(f"/v1/categories/{chemistry_id}", json={"name": "生物"})

    assert response.status_code == 409


def test_rename_category_404_for_missing_category(client: TestClient) -> None:
    response = client.patch("/v1/categories/999999999", json={"name": "新名字"})
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /v1/categories/{id} -- guarded delete (F4)
# ---------------------------------------------------------------------------


async def test_delete_category_removes_row_when_unreferenced(client: TestClient) -> None:
    category_id = await _make_category("生物")

    response = client.delete(f"/v1/categories/{category_id}")

    assert response.status_code == 204
    async with AsyncSessionLocal() as session:
        assert await session.get(Category, category_id) is None


async def test_delete_category_409_when_chunks_reference_it(client: TestClient) -> None:
    category_id = await _make_category("生物")
    document_id = await _make_document()
    await _make_chunk(document_id, category_id)

    response = client.delete(f"/v1/categories/{category_id}")

    assert response.status_code == 409
    async with AsyncSessionLocal() as session:
        assert await session.get(Category, category_id) is not None


async def test_delete_category_409_when_it_has_children(client: TestClient) -> None:
    subject_id = await _make_category("生物")
    await _make_category("光合作用", parent_id=subject_id)

    response = client.delete(f"/v1/categories/{subject_id}")

    assert response.status_code == 409
    async with AsyncSessionLocal() as session:
        assert await session.get(Category, subject_id) is not None


def test_delete_category_404_for_missing_category(client: TestClient) -> None:
    response = client.delete("/v1/categories/999999999")
    assert response.status_code == 404
