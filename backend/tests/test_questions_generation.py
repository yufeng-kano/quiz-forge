"""`generate_questions` job handler (.rule 反偷懶規則: job queue 屬高風險邏輯，
須有測試). The LLM transport is faked exactly like `test_llm_client.py`
(`httpx2.MockTransport`, `openai` talks over `httpx2` not `httpx`) so every
captured request's real `response_format`/`messages` body can be asserted on
per question type — the actual job/selection/schema logic under test is
never mocked away, only the network call is.
"""

import json
import math
from collections.abc import Callable

import httpx2
import openai
from factories import create_job
from sqlalchemy import select

import backend.questions.generation as generation_module
from backend.core.config import Settings
from backend.db.session import AsyncSessionLocal
from backend.jobs.worker import claim_job, run_claimed_job
from backend.llm.client import LLMClient
from backend.models.category import Category
from backend.models.chunk import Chunk
from backend.models.document import Document
from backend.models.job import Job
from backend.models.llm_usage import LlmUsage
from backend.models.question import Question

# One valid canned payload per response-model class name (matches
# `backend.questions.schemas.QUESTION_TYPE_MODELS` values' `__name__`).
CANNED_PAYLOADS: dict[str, dict[str, object]] = {
    "ComparisonQuestion": {
        "type": "comparison",
        "stem": "試比較光合作用與呼吸作用之異同。",
        "subject_a": "光合作用",
        "subject_b": "呼吸作用",
        "aspects": ["場所"],
        "model_answer": {
            "similarities": ["皆為細胞內能量代謝反應"],
            "differences": [{"aspect": "場所", "a": "葉綠體", "b": "粒線體"}],
        },
    },
    "AnalogyQuestion": {
        "type": "analogy",
        "a": "筆",
        "b": "寫字",
        "c": "剪刀",
        "answer": "剪裁",
        "options": None,
        "explanation": None,
    },
    "SingleChoiceQuestion": {
        "type": "single_choice",
        "stem": "光合作用發生在細胞的哪個構造？",
        "options": ["粒線體", "葉綠體", "細胞核", "核糖體"],
        "answer_index": 1,
        "explanation": None,
    },
    "TrueFalseQuestion": {
        "type": "true_false",
        "stem": "光合作用會釋放氧氣。",
        "answer": True,
        "explanation": None,
    },
    "FillBlankQuestion": {
        "type": "fill_blank",
        "stem": "水的化學式為 ____。",
        "answers": ["H2O"],
    },
    "ShortAnswerQuestion": {
        "type": "short_answer",
        "stem": "請說明光合作用的功能。",
        "model_answer": "將光能轉換成化學能。",
        "key_points": ["光能轉化學能"],
    },
}


def _chat_completion_response(*, model: str, content: dict[str, object]) -> httpx2.Response:
    return httpx2.Response(
        200,
        json={
            "id": "chatcmpl-test",
            "object": "chat.completion",
            "created": 0,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": json.dumps(content)},
                }
            ],
            "usage": {"prompt_tokens": 11, "completion_tokens": 22, "total_tokens": 33},
        },
    )


def _canned_handler(
    captured: list[httpx2.Request],
) -> Callable[[httpx2.Request], httpx2.Response]:
    """Serves the canned valid payload matching whatever type the request's
    `response_format.json_schema.name` asked for."""

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured.append(request)
        body = json.loads(request.content)
        schema_name = body["response_format"]["json_schema"]["name"]
        return _chat_completion_response(model=body["model"], content=CANNED_PAYLOADS[schema_name])

    return handler


def _fake_llm_client(handler: Callable[[httpx2.Request], httpx2.Response]) -> LLMClient:
    settings = Settings(
        llm_base_url="https://llm.test/v1",
        llm_api_key="test-key-not-real",
        text_model="test-text-model",
    )
    fake_openai_client = openai.AsyncOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler)),
    )
    return LLMClient(
        settings=settings, session_factory=AsyncSessionLocal, openai_client=fake_openai_client
    )


def _unit_vector(angle_degrees: float, dim: int) -> list[float]:
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


async def _make_category() -> int:
    async with AsyncSessionLocal() as session:
        category = Category(name="分類", parent_id=None)
        session.add(category)
        await session.commit()
        await session.refresh(category)
        return category.id


async def _make_chunk(
    *, document_id: int, category_id: int | None, content: str, embedding: list[float] | None = None
) -> int:
    async with AsyncSessionLocal() as session:
        chunk = Chunk(
            document_id=document_id, content=content, category_id=category_id, embedding=embedding
        )
        session.add(chunk)
        await session.commit()
        await session.refresh(chunk)
        return chunk.id


async def _run_job(payload: dict[str, object]) -> int:
    job_id = await create_job("generate_questions", payload=payload)
    async with AsyncSessionLocal() as session:
        claimed = await claim_job(session)
        assert claimed is not None
        assert claimed.id == job_id
    await run_claimed_job(AsyncSessionLocal, job_id)
    return job_id


async def _get_job(job_id: int) -> Job:
    async with AsyncSessionLocal() as session:
        job = await session.get(Job, job_id)
        assert job is not None
        return job


async def _questions_for_type(question_type: str) -> list[Question]:
    async with AsyncSessionLocal() as session:
        rows = (
            (await session.execute(select(Question).where(Question.type == question_type)))
            .scalars()
            .all()
        )
        return list(rows)


async def test_single_choice_generates_drafts_with_correct_json_schema_request(
    monkeypatch,
) -> None:
    document_id = await _make_document()
    category_id = await _make_category()
    await _make_chunk(document_id=document_id, category_id=category_id, content="第一段內容")
    await _make_chunk(document_id=document_id, category_id=category_id, content="第二段內容")

    captured: list[httpx2.Request] = []
    fake_client = _fake_llm_client(_canned_handler(captured))
    monkeypatch.setattr(generation_module, "get_llm_client", lambda: fake_client)

    job_id = await _run_job(
        {
            "document_ids": [document_id],
            "category_ids": None,
            "question_type": "single_choice",
            "count": 2,
            "difficulty": "中等",
        }
    )

    job = await _get_job(job_id)
    assert job.status == "done"
    assert job.progress == "2/2"
    assert job.error is None

    assert len(captured) == 2
    for request in captured:
        body = json.loads(request.content)
        json_schema = body["response_format"]["json_schema"]
        assert json_schema["name"] == "SingleChoiceQuestion"
        assert json_schema["strict"] is True
        assert json_schema["schema"]["additionalProperties"] is False
        assert set(json_schema["schema"]["required"]) == {
            "type",
            "stem",
            "options",
            "answer_index",
            "explanation",
        }

    questions = await _questions_for_type("single_choice")
    assert len(questions) == 2
    for question in questions:
        assert question.status == "draft"
        assert question.difficulty == "中等"
        assert "type" not in question.payload
        assert question.payload["answer_index"] == 1
        assert len(question.source_chunk_ids) == 1

    async with AsyncSessionLocal() as session:
        usage_rows = (
            (
                await session.execute(
                    select(LlmUsage).where(LlmUsage.purpose == "generate_question_single_choice")
                )
            )
            .scalars()
            .all()
        )
    assert len(usage_rows) == 2
    assert all(row.prompt_tokens == 11 for row in usage_rows)


async def test_comparison_sends_both_chunk_contents_and_pairs_the_source_chunks(
    monkeypatch,
) -> None:
    dim = Settings().embedding_dim
    document_id = await _make_document()
    category_id = await _make_category()
    chunk_a = await _make_chunk(
        document_id=document_id,
        category_id=category_id,
        content="光合作用內容",
        embedding=_unit_vector(0, dim),
    )
    chunk_b = await _make_chunk(
        document_id=document_id,
        category_id=category_id,
        content="呼吸作用內容",
        embedding=_unit_vector(50, dim),  # cos(50°) ≈ 0.64, inside the default band
    )

    captured: list[httpx2.Request] = []
    fake_client = _fake_llm_client(_canned_handler(captured))
    monkeypatch.setattr(generation_module, "get_llm_client", lambda: fake_client)

    job_id = await _run_job(
        {
            "document_ids": [document_id],
            "category_ids": None,
            "question_type": "comparison",
            "count": 1,
            "difficulty": None,
        }
    )

    job = await _get_job(job_id)
    assert job.status == "done"
    assert job.error is None

    assert len(captured) == 1
    body = json.loads(captured[0].content)
    assert body["response_format"]["json_schema"]["name"] == "ComparisonQuestion"
    prompt_text = body["messages"][0]["content"]
    assert "光合作用內容" in prompt_text
    assert "呼吸作用內容" in prompt_text

    questions = await _questions_for_type("comparison")
    assert len(questions) == 1
    assert set(questions[0].source_chunk_ids) == {chunk_a, chunk_b}


async def test_one_bad_generation_does_not_abort_the_rest_of_the_batch(monkeypatch) -> None:
    document_id = await _make_document()
    category_id = await _make_category()
    for i in range(3):
        await _make_chunk(document_id=document_id, category_id=category_id, content=f"內容{i}")

    call_count = 0

    def handler(request: httpx2.Request) -> httpx2.Response:
        nonlocal call_count
        call_count += 1
        body = json.loads(request.content)
        if call_count == 2:
            # Missing required "answer_index" -- fails schema validation.
            broken = {
                "type": "single_choice",
                "stem": "...",
                "options": ["a", "b"],
                "explanation": None,
            }
            return _chat_completion_response(model=body["model"], content=broken)
        return _chat_completion_response(
            model=body["model"], content=CANNED_PAYLOADS["SingleChoiceQuestion"]
        )

    fake_client = _fake_llm_client(handler)
    monkeypatch.setattr(generation_module, "get_llm_client", lambda: fake_client)

    job_id = await _run_job(
        {
            "document_ids": [document_id],
            "category_ids": None,
            "question_type": "single_choice",
            "count": 3,
            "difficulty": None,
        }
    )

    job = await _get_job(job_id)
    # 2 of 3 succeeded -> job still reaches "done", not "failed" (.rule:
    # 一題失敗不得整批重跑；job.error carries the failure summary instead).
    assert job.status == "done"
    assert job.progress == "3/3"
    assert job.error is not None
    assert "1/3" in job.error

    questions = await _questions_for_type("single_choice")
    assert len(questions) == 2


async def test_all_generations_failing_marks_the_job_failed(monkeypatch) -> None:
    document_id = await _make_document()
    category_id = await _make_category()
    await _make_chunk(document_id=document_id, category_id=category_id, content="內容")

    def handler(request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content)
        broken: dict[str, object] = {
            "type": "single_choice",
            "stem": "...",
        }  # missing required fields
        return _chat_completion_response(model=body["model"], content=broken)

    fake_client = _fake_llm_client(handler)
    monkeypatch.setattr(generation_module, "get_llm_client", lambda: fake_client)

    job_id = await _run_job(
        {
            "document_ids": [document_id],
            "category_ids": None,
            "question_type": "single_choice",
            "count": 1,
            "difficulty": None,
        }
    )

    job = await _get_job(job_id)
    assert job.status == "failed"
    assert job.error is not None
    assert "failed" in job.error.lower()

    questions = await _questions_for_type("single_choice")
    assert len(questions) == 0


async def test_no_eligible_material_marks_the_job_failed(monkeypatch) -> None:
    document_id = await _make_document()  # no chunks at all

    captured: list[httpx2.Request] = []
    fake_client = _fake_llm_client(_canned_handler(captured))
    monkeypatch.setattr(generation_module, "get_llm_client", lambda: fake_client)

    job_id = await _run_job(
        {
            "document_ids": [document_id],
            "category_ids": None,
            "question_type": "single_choice",
            "count": 2,
            "difficulty": None,
        }
    )

    job = await _get_job(job_id)
    assert job.status == "failed"
    assert job.error is not None
    assert "no eligible source material" in job.error
    assert captured == []  # never even reached the LLM


async def test_unknown_question_type_marks_the_job_failed(monkeypatch) -> None:
    document_id = await _make_document()
    await _make_chunk(document_id=document_id, category_id=None, content="內容")

    captured: list[httpx2.Request] = []
    fake_client = _fake_llm_client(_canned_handler(captured))
    monkeypatch.setattr(generation_module, "get_llm_client", lambda: fake_client)

    job_id = await _run_job(
        {
            "document_ids": [document_id],
            "category_ids": None,
            "question_type": "essay",
            "count": 1,
            "difficulty": None,
        }
    )

    job = await _get_job(job_id)
    assert job.status == "failed"
    assert job.error is not None
    assert "unknown question type" in job.error
    assert captured == []
