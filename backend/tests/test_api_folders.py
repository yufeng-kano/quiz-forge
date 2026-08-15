"""`/v1/folders` through the real HTTP app: `GET` (list w/ document counts),
`POST` (create, case-sensitive unique name), `PATCH` (rename), `DELETE`
(always allowed -- documents fall back to unfiled) (docs/ingestion.md 文件
管理；docs/data-model.md `folders`)."""

from fastapi.testclient import TestClient

from backend.db.session import AsyncSessionLocal
from backend.models.document import Document
from backend.models.folder import Folder


async def _make_folder(name: str) -> int:
    async with AsyncSessionLocal() as session:
        folder = Folder(name=name)
        session.add(folder)
        await session.commit()
        await session.refresh(folder)
        return folder.id


async def _make_document(title: str, folder_id: int | None = None) -> int:
    async with AsyncSessionLocal() as session:
        document = Document(
            source_type="upload", title=title, status="ready", folder_id=folder_id
        )
        session.add(document)
        await session.commit()
        await session.refresh(document)
        return document.id


# ---------------------------------------------------------------------------
# GET /v1/folders -- list w/ per-folder document count
# ---------------------------------------------------------------------------


def test_list_folders_empty_when_none_exist(client: TestClient) -> None:
    response = client.get("/v1/folders")
    assert response.status_code == 200
    assert response.json() == []


async def test_list_folders_reports_document_counts(client: TestClient) -> None:
    folder_id = await _make_folder("教材")
    empty_folder_id = await _make_folder("空資料夾")
    await _make_document("doc-a", folder_id=folder_id)
    await _make_document("doc-b", folder_id=folder_id)
    await _make_document("doc-c")  # unfiled -- must not count toward any folder

    response = client.get("/v1/folders")

    assert response.status_code == 200
    by_id = {row["id"]: row for row in response.json()}
    assert by_id[folder_id]["name"] == "教材"
    assert by_id[folder_id]["document_count"] == 2
    assert by_id[empty_folder_id]["document_count"] == 0


# ---------------------------------------------------------------------------
# POST /v1/folders -- create
# ---------------------------------------------------------------------------


def test_create_folder_returns_new_folder_with_zero_documents(client: TestClient) -> None:
    response = client.post("/v1/folders", json={"name": "教材"})

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "教材"
    assert body["document_count"] == 0
    assert isinstance(body["id"], int)


def test_create_folder_strips_whitespace(client: TestClient) -> None:
    response = client.post("/v1/folders", json={"name": "  教材  "})

    assert response.status_code == 201
    assert response.json()["name"] == "教材"


def test_create_folder_rejects_blank_name(client: TestClient) -> None:
    response = client.post("/v1/folders", json={"name": "   "})
    assert response.status_code == 422


async def test_create_folder_409_on_duplicate_name(client: TestClient) -> None:
    await _make_folder("教材")

    response = client.post("/v1/folders", json={"name": "教材"})

    assert response.status_code == 409


async def test_create_folder_name_uniqueness_is_case_sensitive(client: TestClient) -> None:
    """Chosen uniqueness rule for this feature (task spec) — a same-name
    folder differing only in case is allowed, not treated as a duplicate."""
    await _make_folder("教材")

    response = client.post("/v1/folders", json={"name": "Notes"})
    assert response.status_code == 201

    response = client.post("/v1/folders", json={"name": "notes"})
    assert response.status_code == 201


# ---------------------------------------------------------------------------
# PATCH /v1/folders/{id} -- rename
# ---------------------------------------------------------------------------


async def test_rename_folder_updates_name(client: TestClient) -> None:
    folder_id = await _make_folder("教材")

    response = client.patch(f"/v1/folders/{folder_id}", json={"name": "課程資料"})

    assert response.status_code == 200
    assert response.json()["name"] == "課程資料"
    async with AsyncSessionLocal() as session:
        folder = await session.get(Folder, folder_id)
        assert folder is not None
        assert folder.name == "課程資料"


async def test_rename_folder_reports_document_count(client: TestClient) -> None:
    folder_id = await _make_folder("教材")
    await _make_document("doc-a", folder_id=folder_id)

    response = client.patch(f"/v1/folders/{folder_id}", json={"name": "課程資料"})

    assert response.status_code == 200
    assert response.json()["document_count"] == 1


def test_rename_folder_rejects_blank_name(client: TestClient) -> None:
    response = client.patch("/v1/folders/1", json={"name": "   "})
    assert response.status_code == 422


async def test_rename_folder_409_on_duplicate_name(client: TestClient) -> None:
    await _make_folder("教材")
    other_id = await _make_folder("課程資料")

    response = client.patch(f"/v1/folders/{other_id}", json={"name": "教材"})

    assert response.status_code == 409


async def test_rename_folder_allows_renaming_to_its_own_current_name(client: TestClient) -> None:
    folder_id = await _make_folder("教材")

    response = client.patch(f"/v1/folders/{folder_id}", json={"name": "教材"})

    assert response.status_code == 200


def test_rename_folder_404_for_missing_folder(client: TestClient) -> None:
    response = client.patch("/v1/folders/999999999", json={"name": "新名字"})
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /v1/folders/{id} -- always allowed, unfiles documents
# ---------------------------------------------------------------------------


async def test_delete_folder_removes_row(client: TestClient) -> None:
    folder_id = await _make_folder("教材")

    response = client.delete(f"/v1/folders/{folder_id}")

    assert response.status_code == 204
    async with AsyncSessionLocal() as session:
        assert await session.get(Folder, folder_id) is None


async def test_delete_folder_unfiles_its_documents(client: TestClient) -> None:
    folder_id = await _make_folder("教材")
    document_id = await _make_document("doc-a", folder_id=folder_id)

    response = client.delete(f"/v1/folders/{folder_id}")

    assert response.status_code == 204
    async with AsyncSessionLocal() as session:
        document = await session.get(Document, document_id)
        assert document is not None
        assert document.folder_id is None
        assert await session.get(Folder, folder_id) is None


def test_delete_folder_404_for_missing_folder(client: TestClient) -> None:
    response = client.delete("/v1/folders/999999999")
    assert response.status_code == 404
