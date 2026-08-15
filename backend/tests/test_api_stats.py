"""`GET /v1/stats` through the real HTTP app (F5 — Dashboard overview)."""

from factories import create_job, create_llm_usage
from fastapi.testclient import TestClient

from backend.db.session import AsyncSessionLocal
from backend.models.category import Category
from backend.models.chunk import Chunk
from backend.models.document import Document
from backend.models.question import Question

SINGLE_CHOICE_PAYLOAD: dict[str, object] = {
    "stem": "...",
    "options": ["a", "b"],
    "answer_index": 0,
    "explanation": None,
}


async def _make_document(status: str) -> int:
    async with AsyncSessionLocal() as session:
        document = Document(source_type="upload", title="doc", status=status)
        session.add(document)
        await session.commit()
        await session.refresh(document)
        return document.id


async def _make_category(name: str) -> int:
    async with AsyncSessionLocal() as session:
        category = Category(name=name, parent_id=None)
        session.add(category)
        await session.commit()
        await session.refresh(category)
        return category.id


async def _make_chunk(document_id: int, category_id: int | None) -> int:
    async with AsyncSessionLocal() as session:
        chunk = Chunk(document_id=document_id, content="內容", category_id=category_id)
        session.add(chunk)
        await session.commit()
        await session.refresh(chunk)
        return chunk.id


async def _make_question(status: str) -> int:
    async with AsyncSessionLocal() as session:
        question = Question(
            type="single_choice", status=status, payload=SINGLE_CHOICE_PAYLOAD, source_chunk_ids=[]
        )
        session.add(question)
        await session.commit()
        await session.refresh(question)
        return question.id


def test_stats_all_zero_on_empty_database(client: TestClient) -> None:
    response = client.get("/v1/stats")

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "documents_by_status": {},
        "questions_by_status": {},
        "chunk_count": 0,
        "category_count": 0,
        "failed_job_count": 0,
        "llm_call_count": 0,
        "llm_prompt_tokens": 0,
        "llm_completion_tokens": 0,
    }


async def test_stats_counts_documents_by_status(client: TestClient) -> None:
    await _make_document("ready")
    await _make_document("ready")
    await _make_document("failed")

    response = client.get("/v1/stats")

    assert response.status_code == 200
    assert response.json()["documents_by_status"] == {"ready": 2, "failed": 1}


async def test_stats_counts_questions_by_status(client: TestClient) -> None:
    await _make_question("draft")
    await _make_question("approved")
    await _make_question("approved")

    response = client.get("/v1/stats")

    assert response.status_code == 200
    assert response.json()["questions_by_status"] == {"draft": 1, "approved": 2}


async def test_stats_counts_chunks_and_categories(client: TestClient) -> None:
    document_id = await _make_document("ready")
    category_id = await _make_category("生物")
    await _make_chunk(document_id, category_id)
    await _make_chunk(document_id, category_id)

    response = client.get("/v1/stats")

    assert response.status_code == 200
    body = response.json()
    assert body["chunk_count"] == 2
    assert body["category_count"] == 1


async def test_stats_counts_only_failed_jobs(client: TestClient) -> None:
    await create_job("parse_document", status="failed")
    await create_job("parse_document", status="failed")
    await create_job("parse_document", status="done")
    await create_job("parse_document", status="pending")

    response = client.get("/v1/stats")

    assert response.status_code == 200
    assert response.json()["failed_job_count"] == 2


async def test_stats_sums_llm_usage_across_calls(client: TestClient) -> None:
    await create_llm_usage(
        model="m1", purpose="p1", prompt_tokens=10, completion_tokens=5
    )
    await create_llm_usage(
        model="m2", purpose="p2", prompt_tokens=7, completion_tokens=3
    )

    response = client.get("/v1/stats")

    assert response.status_code == 200
    body = response.json()
    assert body["llm_call_count"] == 2
    assert body["llm_prompt_tokens"] == 17
    assert body["llm_completion_tokens"] == 8
