"""`POST /v1/generate` and `/v1/questions` through the real HTTP app.

The `client` fixture disables the job worker pool, so `POST /v1/generate`
here only exercises row/job creation (the `generate_questions` handler
itself, including its LLM calls, is covered against a mocked transport in
`test_questions_generation.py` and against the live provider in the e2e
run — see task report)."""

from fastapi.testclient import TestClient

from backend.db.session import AsyncSessionLocal
from backend.models.category import Category
from backend.models.chunk import Chunk
from backend.models.document import Document
from backend.models.job import Job
from backend.models.question import Question


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


async def _make_chunk(document_id: int, category_id: int | None, content: str = "內容") -> int:
    async with AsyncSessionLocal() as session:
        chunk = Chunk(document_id=document_id, content=content, category_id=category_id)
        session.add(chunk)
        await session.commit()
        await session.refresh(chunk)
        return chunk.id


async def _make_question(
    *,
    question_type: str = "single_choice",
    status: str = "draft",
    difficulty: str | None = None,
    payload: dict[str, object] | None = None,
    source_chunk_ids: list[int] | None = None,
) -> int:
    async with AsyncSessionLocal() as session:
        question = Question(
            type=question_type,
            status=status,
            difficulty=difficulty,
            payload=payload
            or {
                "stem": "...",
                "options": ["a", "b", "c", "d"],
                "answer_index": 0,
                "explanation": None,
            },
            source_chunk_ids=source_chunk_ids or [],
        )
        session.add(question)
        await session.commit()
        await session.refresh(question)
        return question.id


# ---------------------------------------------------------------------------
# POST /v1/generate
# ---------------------------------------------------------------------------


async def test_create_generation_job_enqueues_job_with_scope(client: TestClient) -> None:
    document_id = await _make_document()

    response = client.post(
        "/v1/generate",
        json={
            "document_ids": [document_id],
            "question_type": "single_choice",
            "count": 3,
            "difficulty": "簡單",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert isinstance(body["job_id"], int)

    async with AsyncSessionLocal() as session:
        job = await session.get(Job, body["job_id"])
        assert job is not None
        assert job.kind == "generate_questions"
        assert job.status == "pending"
        assert job.payload == {
            "document_ids": [document_id],
            "category_ids": None,
            "question_type": "single_choice",
            "count": 3,
            "difficulty": "簡單",
        }


def test_create_generation_job_rejects_empty_scope(client: TestClient) -> None:
    response = client.post(
        "/v1/generate",
        json={"question_type": "single_choice", "count": 1},
    )
    assert response.status_code == 422


def test_create_generation_job_rejects_non_positive_count(client: TestClient) -> None:
    response = client.post(
        "/v1/generate",
        json={"document_ids": [1], "question_type": "single_choice", "count": 0},
    )
    assert response.status_code == 422


def test_create_generation_job_rejects_unknown_question_type(client: TestClient) -> None:
    response = client.post(
        "/v1/generate",
        json={"document_ids": [1], "question_type": "essay", "count": 1},
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /v1/questions
# ---------------------------------------------------------------------------


async def test_list_questions_filters_by_status(client: TestClient) -> None:
    draft_id = await _make_question(status="draft")
    await _make_question(status="approved")

    response = client.get("/v1/questions", params={"status": "draft"})

    assert response.status_code == 200
    body = response.json()
    assert [item["id"] for item in body] == [draft_id]


async def test_list_questions_filters_by_type(client: TestClient) -> None:
    tf_id = await _make_question(
        question_type="true_false", payload={"stem": "...", "answer": True, "explanation": None}
    )
    await _make_question(question_type="single_choice")

    response = client.get("/v1/questions", params={"type": "true_false"})

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [tf_id]


async def test_list_questions_filters_by_difficulty(client: TestClient) -> None:
    hard_id = await _make_question(difficulty="困難")
    await _make_question(difficulty="簡單")

    response = client.get("/v1/questions", params={"difficulty": "困難"})

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [hard_id]


async def test_list_questions_filters_by_category_via_source_chunks(client: TestClient) -> None:
    document_id = await _make_document()
    category_a = await _make_category("分類甲")
    category_b = await _make_category("分類乙")
    chunk_a = await _make_chunk(document_id, category_a)
    chunk_b = await _make_chunk(document_id, category_b)

    in_category_a = await _make_question(source_chunk_ids=[chunk_a])
    await _make_question(source_chunk_ids=[chunk_b])

    response = client.get("/v1/questions", params={"category_id": category_a})

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [in_category_a]


async def test_list_questions_newest_first(client: TestClient) -> None:
    first_id = await _make_question()
    second_id = await _make_question()

    response = client.get("/v1/questions")

    ids = [item["id"] for item in response.json()]
    assert ids.index(second_id) < ids.index(first_id)


async def test_list_questions_includes_payload(client: TestClient) -> None:
    question_id = await _make_question()
    response = client.get("/v1/questions")
    item = next(item for item in response.json() if item["id"] == question_id)
    assert item["payload"]["answer_index"] == 0


# ---------------------------------------------------------------------------
# GET /v1/questions/{id}
# ---------------------------------------------------------------------------


async def test_get_question_detail_includes_source_chunk_text(client: TestClient) -> None:
    document_id = await _make_document()
    chunk_id = await _make_chunk(document_id, None, content="原文內容在這裡")
    question_id = await _make_question(source_chunk_ids=[chunk_id])

    response = client.get(f"/v1/questions/{question_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["source_chunks"] == [{"id": chunk_id, "content": "原文內容在這裡"}]


def test_get_question_404_for_missing_question(client: TestClient) -> None:
    response = client.get("/v1/questions/999999999")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /v1/questions/{id}
# ---------------------------------------------------------------------------


async def test_patch_question_updates_valid_payload(client: TestClient) -> None:
    question_id = await _make_question()

    response = client.patch(
        f"/v1/questions/{question_id}",
        json={
            "payload": {
                "stem": "修改後的題幹",
                "options": ["x", "y"],
                "answer_index": 1,
                "explanation": None,
            }
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["payload"]["stem"] == "修改後的題幹"
    assert "type" not in body["payload"]


async def test_patch_question_rejects_invalid_payload_shape_with_422(client: TestClient) -> None:
    question_id = await _make_question()

    response = client.patch(
        f"/v1/questions/{question_id}",
        json={"payload": {"stem": "...", "options": ["only-one"], "answer_index": 0}},
    )

    assert response.status_code == 422


async def test_patch_question_rejects_out_of_range_answer_index_with_422(
    client: TestClient,
) -> None:
    question_id = await _make_question()

    response = client.patch(
        f"/v1/questions/{question_id}",
        json={
            "payload": {
                "stem": "...",
                "options": ["a", "b"],
                "answer_index": 5,
                "explanation": None,
            }
        },
    )

    assert response.status_code == 422


async def test_patch_question_updates_difficulty_only(client: TestClient) -> None:
    question_id = await _make_question(difficulty="簡單")

    response = client.patch(f"/v1/questions/{question_id}", json={"difficulty": "困難"})

    assert response.status_code == 200
    body = response.json()
    assert body["difficulty"] == "困難"
    assert body["payload"]["answer_index"] == 0  # untouched


async def test_patch_question_can_clear_difficulty_to_null(client: TestClient) -> None:
    question_id = await _make_question(difficulty="簡單")

    response = client.patch(f"/v1/questions/{question_id}", json={"difficulty": None})

    assert response.status_code == 200
    assert response.json()["difficulty"] is None


def test_patch_question_404_for_missing_question(client: TestClient) -> None:
    response = client.patch("/v1/questions/999999999", json={"difficulty": "簡單"})
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# approve / reject state machine
# ---------------------------------------------------------------------------


async def test_approve_draft_question(client: TestClient) -> None:
    question_id = await _make_question(status="draft")
    response = client.post(f"/v1/questions/{question_id}/approve")
    assert response.status_code == 200
    assert response.json()["status"] == "approved"


async def test_approve_already_approved_question_returns_409(client: TestClient) -> None:
    question_id = await _make_question(status="approved")
    response = client.post(f"/v1/questions/{question_id}/approve")
    assert response.status_code == 409


async def test_approve_rejected_question_returns_409(client: TestClient) -> None:
    question_id = await _make_question(status="rejected")
    response = client.post(f"/v1/questions/{question_id}/approve")
    assert response.status_code == 409


async def test_reject_draft_question(client: TestClient) -> None:
    question_id = await _make_question(status="draft")
    response = client.post(f"/v1/questions/{question_id}/reject")
    assert response.status_code == 200
    assert response.json()["status"] == "rejected"


async def test_reject_approved_question(client: TestClient) -> None:
    question_id = await _make_question(status="approved")
    response = client.post(f"/v1/questions/{question_id}/reject")
    assert response.status_code == 200
    assert response.json()["status"] == "rejected"


async def test_reject_rejected_question_undoes_back_to_draft(client: TestClient) -> None:
    question_id = await _make_question(status="rejected")
    response = client.post(f"/v1/questions/{question_id}/reject")
    assert response.status_code == 200
    assert response.json()["status"] == "draft"


async def test_approve_then_reject_then_undo_round_trip(client: TestClient) -> None:
    question_id = await _make_question(status="draft")

    approved = client.post(f"/v1/questions/{question_id}/approve")
    assert approved.json()["status"] == "approved"

    rejected = client.post(f"/v1/questions/{question_id}/reject")
    assert rejected.json()["status"] == "rejected"

    undone = client.post(f"/v1/questions/{question_id}/reject")
    assert undone.json()["status"] == "draft"

    reapproved = client.post(f"/v1/questions/{question_id}/approve")
    assert reapproved.json()["status"] == "approved"


def test_approve_404_for_missing_question(client: TestClient) -> None:
    response = client.post("/v1/questions/999999999/approve")
    assert response.status_code == 404


def test_reject_404_for_missing_question(client: TestClient) -> None:
    response = client.post("/v1/questions/999999999/reject")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /v1/questions/{id}
# ---------------------------------------------------------------------------


async def test_delete_question_removes_row(client: TestClient) -> None:
    question_id = await _make_question()

    response = client.delete(f"/v1/questions/{question_id}")
    assert response.status_code == 204

    async with AsyncSessionLocal() as session:
        assert await session.get(Question, question_id) is None


def test_delete_question_404_for_missing_question(client: TestClient) -> None:
    response = client.delete("/v1/questions/999999999")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# approved-only export scope sanity check (docs/question-bank.md 審題流程)
# ---------------------------------------------------------------------------


async def test_get_approved_questions_after_approve_flow(client: TestClient) -> None:
    question_id = await _make_question(status="draft")
    client.post(f"/v1/questions/{question_id}/approve")

    response = client.get("/v1/questions", params={"status": "approved"})

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [question_id]
