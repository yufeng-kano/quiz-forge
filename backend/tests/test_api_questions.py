"""`POST /v1/generate` and `/v1/questions` through the real HTTP app.

The `client` fixture disables the job worker pool, so `POST /v1/generate`
here only exercises row/job creation (the `generate_questions` handler
itself, including its LLM calls, is covered against a mocked transport in
`test_questions_generation.py` and against the live provider in the e2e
run — see task report). `GET /v1/questions?similar_to=...` does call the LLM
client synchronously in the request path (docs/question-bank.md 題目向量化與
語意搜尋 D3) -- those tests fake it the same way `test_questions_generation.py`
does (a real `LLMClient` over an `httpx2.MockTransport`), monkeypatched onto
`backend.api.v1.questions.get_llm_client`."""

import json
import math

import httpx2
import openai
from fastapi.testclient import TestClient
from sqlalchemy import select

import backend.api.v1.questions as questions_module
from backend.core.config import Settings
from backend.db.session import AsyncSessionLocal
from backend.llm.client import LLMClient
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
    embedding: list[float] | None = None,
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
            embedding=embedding,
        )
        session.add(question)
        await session.commit()
        await session.refresh(question)
        return question.id


async def _get_question_row(question_id: int) -> Question:
    async with AsyncSessionLocal() as session:
        question = await session.get(Question, question_id)
        assert question is not None
        return question


async def _embed_question_job_payloads() -> list[dict[str, object]]:
    """Every enqueued `embed_questions` job's payload, in creation order —
    used to assert a `POST`/`PATCH` enqueued exactly one, for exactly the
    right question id(s)."""
    async with AsyncSessionLocal() as session:
        jobs = (
            (
                await session.execute(
                    select(Job).where(Job.kind == "embed_questions").order_by(Job.id)
                )
            )
            .scalars()
            .all()
        )
        return [job.payload for job in jobs]


def _unit_vector(angle_degrees: float, dim: int) -> list[float]:
    radians = math.radians(angle_degrees)
    vector = [0.0] * dim
    vector[0] = math.cos(radians)
    vector[1] = math.sin(radians)
    return vector


def _embeddings_response(*, model: str, vector: list[float]) -> httpx2.Response:
    return httpx2.Response(
        200,
        json={
            "object": "list",
            "model": model,
            "data": [{"object": "embedding", "index": 0, "embedding": vector}],
            "usage": {"prompt_tokens": 2, "total_tokens": 2},
        },
    )


def _fake_embed_client_returning(vector: list[float]) -> LLMClient:
    """A fake `LLMClient` (real `LLMClient` over an `httpx2.MockTransport`,
    same pattern as `test_questions_generation.py`) whose `embed()` always
    answers with `vector`, regardless of the input text — enough for
    `similar_to` tests, which only ever embed the one free-text query per
    request."""

    def handler(request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content)
        return _embeddings_response(model=body["model"], vector=vector)

    settings = Settings(llm_base_url="https://llm.test/v1", llm_api_key="test-key-not-real")
    fake_openai_client = openai.AsyncOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler)),
    )
    return LLMClient(
        settings=settings, session_factory=AsyncSessionLocal, openai_client=fake_openai_client
    )


# ---------------------------------------------------------------------------
# POST /v1/generate
# ---------------------------------------------------------------------------


async def test_create_generation_job_enqueues_job_with_scope(client: TestClient) -> None:
    document_id = await _make_document()

    response = client.post(
        "/v1/generate",
        json={
            "document_ids": [document_id],
            "items": [{"question_type": "single_choice", "count": 3}],
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
            "items": [{"question_type": "single_choice", "count": 3}],
            "difficulty": "簡單",
        }


async def test_create_generation_job_enqueues_job_with_multiple_combos(
    client: TestClient,
) -> None:
    document_id = await _make_document()

    response = client.post(
        "/v1/generate",
        json={
            "document_ids": [document_id],
            "items": [
                {"question_type": "single_choice", "count": 10},
                {"question_type": "true_false", "count": 5},
                {"question_type": "short_answer", "count": 2},
            ],
        },
    )

    assert response.status_code == 201
    body = response.json()

    async with AsyncSessionLocal() as session:
        job = await session.get(Job, body["job_id"])
        assert job is not None
        assert job.payload["items"] == [
            {"question_type": "single_choice", "count": 10},
            {"question_type": "true_false", "count": 5},
            {"question_type": "short_answer", "count": 2},
        ]


def test_create_generation_job_rejects_empty_scope(client: TestClient) -> None:
    response = client.post(
        "/v1/generate",
        json={"items": [{"question_type": "single_choice", "count": 1}]},
    )
    assert response.status_code == 422


def test_create_generation_job_rejects_empty_items(client: TestClient) -> None:
    response = client.post(
        "/v1/generate",
        json={"document_ids": [1], "items": []},
    )
    assert response.status_code == 422


def test_create_generation_job_rejects_duplicate_question_type_across_items(
    client: TestClient,
) -> None:
    response = client.post(
        "/v1/generate",
        json={
            "document_ids": [1],
            "items": [
                {"question_type": "single_choice", "count": 3},
                {"question_type": "single_choice", "count": 2},
            ],
        },
    )
    assert response.status_code == 422


def test_create_generation_job_rejects_non_positive_count(client: TestClient) -> None:
    response = client.post(
        "/v1/generate",
        json={"document_ids": [1], "items": [{"question_type": "single_choice", "count": 0}]},
    )
    assert response.status_code == 422


def test_create_generation_job_rejects_unknown_question_type(client: TestClient) -> None:
    response = client.post(
        "/v1/generate",
        json={"document_ids": [1], "items": [{"question_type": "essay", "count": 1}]},
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
    assert [item["id"] for item in body["items"]] == [draft_id]
    assert body["total"] == 1


async def test_list_questions_filters_by_type(client: TestClient) -> None:
    tf_id = await _make_question(
        question_type="true_false", payload={"stem": "...", "answer": True, "explanation": None}
    )
    await _make_question(question_type="single_choice")

    response = client.get("/v1/questions", params={"type": "true_false"})

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == [tf_id]


async def test_list_questions_filters_by_difficulty(client: TestClient) -> None:
    hard_id = await _make_question(difficulty="困難")
    await _make_question(difficulty="簡單")

    response = client.get("/v1/questions", params={"difficulty": "困難"})

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == [hard_id]


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
    body = response.json()
    assert [item["id"] for item in body["items"]] == [in_category_a]
    assert body["total"] == 1


async def test_list_questions_newest_first(client: TestClient) -> None:
    first_id = await _make_question()
    second_id = await _make_question()

    response = client.get("/v1/questions")

    ids = [item["id"] for item in response.json()["items"]]
    assert ids.index(second_id) < ids.index(first_id)


async def test_list_questions_includes_payload(client: TestClient) -> None:
    question_id = await _make_question()
    response = client.get("/v1/questions")
    item = next(item for item in response.json()["items"] if item["id"] == question_id)
    assert item["payload"]["answer_index"] == 0


# ---------------------------------------------------------------------------
# GET /v1/questions -- pagination (F3)
# ---------------------------------------------------------------------------


async def test_list_questions_pagination_envelope_default_limit(client: TestClient) -> None:
    question_id = await _make_question()

    response = client.get("/v1/questions")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["offset"] == 0
    assert body["limit"] > 0  # settings-driven default, not asserting the exact number
    assert [item["id"] for item in body["items"]] == [question_id]


async def test_list_questions_limit_caps_items_but_total_reflects_full_count(
    client: TestClient,
) -> None:
    ids = [await _make_question() for _ in range(3)]

    response = client.get("/v1/questions", params={"limit": 2})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert body["limit"] == 2
    assert len(body["items"]) == 2
    assert [item["id"] for item in body["items"]] == list(reversed(ids))[:2]


async def test_list_questions_offset_advances_the_page(client: TestClient) -> None:
    ids = [await _make_question() for _ in range(3)]

    response = client.get("/v1/questions", params={"limit": 2, "offset": 2})

    assert response.status_code == 200
    body = response.json()
    assert body["offset"] == 2
    assert [item["id"] for item in body["items"]] == [ids[0]]  # oldest, last page


def test_list_questions_rejects_limit_above_settings_max(client: TestClient) -> None:
    response = client.get("/v1/questions", params={"limit": 999999})
    assert response.status_code == 422


async def test_list_questions_unembedded_total_counts_null_embedding_rows(
    client: TestClient,
) -> None:
    """`unembedded_total` (docs/question-bank.md 題目向量化與語意搜尋) is
    present and correct even when `similar_to` was never given."""
    dim = questions_module.get_settings().embedding_dim
    await _make_question(embedding=None)
    await _make_question(embedding=_unit_vector(0, dim))
    await _make_question(embedding=None)

    response = client.get("/v1/questions")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert body["unembedded_total"] == 2


async def test_list_questions_unembedded_total_respects_hard_filters(
    client: TestClient,
) -> None:
    """`unembedded_total` only counts rows matching the non-semantic filters
    (status/type/difficulty/category_id/q) already in effect, not every
    unembedded question in the whole bank."""
    await _make_question(status="draft", embedding=None)
    await _make_question(status="approved", embedding=None)

    response = client.get("/v1/questions", params={"status": "approved"})

    assert response.status_code == 200
    assert response.json()["unembedded_total"] == 1


# ---------------------------------------------------------------------------
# GET /v1/questions -- q search (F3)
# ---------------------------------------------------------------------------


async def test_list_questions_q_searches_payload_text_case_insensitively(
    client: TestClient,
) -> None:
    matching_id = await _make_question(
        payload={
            "stem": "光合作用發生在哪裡？",
            "options": ["葉綠體", "粒線體"],
            "answer_index": 0,
            "explanation": None,
        }
    )
    await _make_question(
        payload={
            "stem": "細胞呼吸的產物是什麼？",
            "options": ["水", "二氧化碳"],
            "answer_index": 0,
            "explanation": None,
        }
    )

    response = client.get("/v1/questions", params={"q": "光合作用"})

    assert response.status_code == 200
    body = response.json()
    assert [item["id"] for item in body["items"]] == [matching_id]
    assert body["total"] == 1


async def test_list_questions_q_matches_nothing_returns_empty_envelope(
    client: TestClient,
) -> None:
    await _make_question()

    response = client.get("/v1/questions", params={"q": "不存在的字串xyz"})

    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["total"] == 0


# ---------------------------------------------------------------------------
# GET /v1/questions -- similar_to semantic search (D3)
# ---------------------------------------------------------------------------


async def test_list_questions_similar_to_orders_by_similarity_and_applies_threshold(
    client: TestClient, monkeypatch
) -> None:
    """docs/question-bank.md 題目向量化與語意搜尋 D3: `similar_to` embeds the
    query once, orders by cosine similarity descending, drops rows below
    `QUESTION_SIMILARITY_MIN` (default 0.2) and rows with a `NULL`
    embedding — while every other filter still applies."""
    dim = questions_module.get_settings().embedding_dim
    query_vector = _unit_vector(0, dim)
    close_id = await _make_question(embedding=_unit_vector(0, dim))  # similarity 1.0
    mid_id = await _make_question(embedding=_unit_vector(60, dim))  # cos(60deg) = 0.5
    await _make_question(embedding=_unit_vector(85, dim))  # cos(85deg) ~= 0.09 -> below 0.2
    await _make_question(embedding=None)  # never embedded -> excluded outright

    fake_client = _fake_embed_client_returning(query_vector)
    monkeypatch.setattr(questions_module, "get_llm_client", lambda: fake_client)

    response = client.get("/v1/questions", params={"similar_to": "光合作用的場所"})

    assert response.status_code == 200
    body = response.json()
    assert [item["id"] for item in body["items"]] == [close_id, mid_id]
    assert body["total"] == 2
    assert body["unembedded_total"] == 1


async def test_list_questions_similar_to_still_applies_q_as_a_hard_filter(
    client: TestClient, monkeypatch
) -> None:
    """`q` and `similar_to` combine: `q` is a literal hard filter, `similar_to`
    only reorders/thresholds what survives it (docs/question-bank.md)."""
    dim = questions_module.get_settings().embedding_dim
    query_vector = _unit_vector(0, dim)
    matching_id = await _make_question(
        embedding=_unit_vector(0, dim),
        payload={
            "stem": "光合作用發生在哪裡？",
            "options": ["葉綠體", "粒線體"],
            "answer_index": 0,
            "explanation": None,
        },
    )
    # High similarity, but fails the literal `q` filter -- must not appear.
    await _make_question(
        embedding=_unit_vector(0, dim),
        payload={
            "stem": "細胞呼吸的產物是什麼？",
            "options": ["水", "二氧化碳"],
            "answer_index": 0,
            "explanation": None,
        },
    )

    fake_client = _fake_embed_client_returning(query_vector)
    monkeypatch.setattr(questions_module, "get_llm_client", lambda: fake_client)

    response = client.get(
        "/v1/questions", params={"similar_to": "光合作用", "q": "光合作用"}
    )

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == [matching_id]


async def test_list_questions_similar_to_all_below_threshold_returns_empty(
    client: TestClient, monkeypatch
) -> None:
    dim = questions_module.get_settings().embedding_dim
    query_vector = _unit_vector(0, dim)
    await _make_question(embedding=_unit_vector(90, dim))  # cos(90deg) = 0.0

    fake_client = _fake_embed_client_returning(query_vector)
    monkeypatch.setattr(questions_module, "get_llm_client", lambda: fake_client)

    response = client.get("/v1/questions", params={"similar_to": "不相關的敘述"})

    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["total"] == 0


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


async def test_patch_question_payload_change_nulls_embedding_and_enqueues_embed_job(
    client: TestClient,
) -> None:
    """docs/question-bank.md 題目向量化與語意搜尋 — 「有動到 payload 時」把
    embedding 設為 NULL 並排一個只含該題 id 的 embed_questions job, never an
    inline embedding call in the request path."""
    dim = questions_module.get_settings().embedding_dim
    question_id = await _make_question(embedding=_unit_vector(0, dim))

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
    stored = await _get_question_row(question_id)
    assert stored.embedding is None

    job_payloads = await _embed_question_job_payloads()
    assert job_payloads == [{"question_ids": [question_id]}]


async def test_patch_question_difficulty_only_does_not_touch_embedding(
    client: TestClient,
) -> None:
    """A `PATCH` that never touches `payload` must not invalidate the
    embedding or enqueue a re-embed job — 只有動到 payload 才重算。"""
    dim = questions_module.get_settings().embedding_dim
    question_id = await _make_question(difficulty="簡單", embedding=_unit_vector(0, dim))

    response = client.patch(f"/v1/questions/{question_id}", json={"difficulty": "困難"})

    assert response.status_code == 200
    stored = await _get_question_row(question_id)
    assert stored.embedding is not None

    assert await _embed_question_job_payloads() == []


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
    assert [item["id"] for item in response.json()["items"]] == [question_id]


# ---------------------------------------------------------------------------
# POST /v1/questions -- manual create (F1)
# ---------------------------------------------------------------------------


def test_create_question_defaults_to_approved_with_empty_source_chunks(
    client: TestClient,
) -> None:
    response = client.post(
        "/v1/questions",
        json={
            "type": "true_false",
            "difficulty": "簡單",
            "payload": {"stem": "地球是圓的。", "answer": True, "explanation": None},
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "approved"
    assert body["type"] == "true_false"
    assert body["difficulty"] == "簡單"
    assert body["source_chunk_ids"] == []
    assert body["payload"]["stem"] == "地球是圓的。"
    assert "type" not in body["payload"]


def test_create_question_can_specify_draft_status(client: TestClient) -> None:
    response = client.post(
        "/v1/questions",
        json={
            "type": "true_false",
            "payload": {"stem": "...", "answer": False, "explanation": None},
            "status": "draft",
        },
    )

    assert response.status_code == 201
    assert response.json()["status"] == "draft"


def test_create_question_rejects_rejected_status(client: TestClient) -> None:
    """`status` is restricted to draft|approved (docs/question-bank.md 手動
    建題) -- `rejected` is not a valid starting state for a brand-new
    question."""
    response = client.post(
        "/v1/questions",
        json={
            "type": "true_false",
            "payload": {"stem": "...", "answer": False, "explanation": None},
            "status": "rejected",
        },
    )
    assert response.status_code == 422


def test_create_question_rejects_invalid_payload_shape_with_422(client: TestClient) -> None:
    response = client.post(
        "/v1/questions",
        json={
            "type": "single_choice",
            "payload": {"stem": "...", "options": ["only-one"], "answer_index": 0},
        },
    )
    assert response.status_code == 422


def test_create_question_rejects_unknown_type(client: TestClient) -> None:
    response = client.post(
        "/v1/questions",
        json={"type": "essay", "payload": {"stem": "..."}},
    )
    assert response.status_code == 422


async def test_created_question_is_persisted_and_listable(client: TestClient) -> None:
    response = client.post(
        "/v1/questions",
        json={
            "type": "fill_blank",
            "payload": {"stem": "水的化學式為 ____。", "answers": ["H2O"]},
        },
    )
    question_id = response.json()["id"]

    async with AsyncSessionLocal() as session:
        stored = await session.get(Question, question_id)
        assert stored is not None
        assert stored.status == "approved"
        assert stored.source_chunk_ids == []


async def test_create_question_enqueues_a_single_question_embed_job(client: TestClient) -> None:
    """docs/question-bank.md 題目向量化與語意搜尋 — manual creation never calls
    the embedding API inline; it enqueues an `embed_questions` job scoped to
    just the new question id."""
    response = client.post(
        "/v1/questions",
        json={
            "type": "true_false",
            "payload": {"stem": "地球是圓的。", "answer": True, "explanation": None},
        },
    )
    question_id = response.json()["id"]

    stored = await _get_question_row(question_id)
    assert stored.embedding is None

    assert await _embed_question_job_payloads() == [{"question_ids": [question_id]}]


# ---------------------------------------------------------------------------
# POST /v1/questions/{id}/duplicate (F1)
# ---------------------------------------------------------------------------


async def test_duplicate_question_creates_draft_copy(client: TestClient) -> None:
    document_id = await _make_document()
    chunk_id = await _make_chunk(document_id, None)
    original_id = await _make_question(
        status="approved", difficulty="困難", source_chunk_ids=[chunk_id]
    )

    response = client.post(f"/v1/questions/{original_id}/duplicate")

    assert response.status_code == 201
    body = response.json()
    assert body["id"] != original_id
    assert body["status"] == "draft"  # always draft regardless of original status
    assert body["type"] == "single_choice"
    assert body["difficulty"] == "困難"
    assert body["source_chunk_ids"] == [chunk_id]  # same source chunks as the original
    assert body["payload"]["answer_index"] == 0


async def test_duplicate_question_does_not_mutate_the_original(client: TestClient) -> None:
    original_id = await _make_question(status="approved")

    client.post(f"/v1/questions/{original_id}/duplicate")

    async with AsyncSessionLocal() as session:
        original = await session.get(Question, original_id)
        assert original is not None
        assert original.status == "approved"


def test_duplicate_question_404_for_missing_question(client: TestClient) -> None:
    response = client.post("/v1/questions/999999999/duplicate")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# POST /v1/questions/embed
# ---------------------------------------------------------------------------


async def test_create_embed_job_with_explicit_question_ids(client: TestClient) -> None:
    response = client.post("/v1/questions/embed", json={"question_ids": [1, 2, 3]})

    assert response.status_code == 201
    body = response.json()
    assert isinstance(body["job_id"], int)

    async with AsyncSessionLocal() as session:
        job = await session.get(Job, body["job_id"])
        assert job is not None
        assert job.kind == "embed_questions"
        assert job.status == "pending"
        assert job.payload == {"question_ids": [1, 2, 3]}


async def test_create_embed_job_with_null_backfills_everything(client: TestClient) -> None:
    response = client.post("/v1/questions/embed", json={})

    assert response.status_code == 201
    async with AsyncSessionLocal() as session:
        job = await session.get(Job, response.json()["job_id"])
        assert job is not None
        assert job.payload == {"question_ids": None}
