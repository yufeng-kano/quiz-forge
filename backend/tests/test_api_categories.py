"""`GET /v1/categories` through the real HTTP app."""

from fastapi.testclient import TestClient

from backend.db.session import AsyncSessionLocal
from backend.models.category import Category


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
