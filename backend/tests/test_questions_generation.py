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
from backend.questions.prompts import build_prompt

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


def _embeddings_response(*, model: str, dim: int) -> httpx2.Response:
    """`generate_questions` embeds every generated question at insertion time
    (docs/question-bank.md 題目向量化與語意搜尋) -- same `httpx2.MockTransport`
    dispatch-by-path pattern as `test_ingestion_pipeline_url_file.py`."""
    return httpx2.Response(
        200,
        json={
            "object": "list",
            "model": model,
            "data": [{"object": "embedding", "index": 0, "embedding": [0.0] * dim}],
            "usage": {"prompt_tokens": 2, "total_tokens": 2},
        },
    )


def _canned_handler(
    captured: list[httpx2.Request], *, dim: int = 1536
) -> Callable[[httpx2.Request], httpx2.Response]:
    """Serves the canned valid payload matching whatever type the request's
    `response_format.json_schema.name` asked for; embeddings calls get a
    canned zero-vector of `dim` dimensions."""

    def handler(request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content)
        if request.url.path == "/v1/embeddings":
            return _embeddings_response(model=body["model"], dim=dim)
        captured.append(request)
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
            "items": [{"question_type": "single_choice", "count": 2}],
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
            "items": [{"question_type": "comparison", "count": 1}],
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
        body = json.loads(request.content)
        if request.url.path == "/v1/embeddings":
            return _embeddings_response(model=body["model"], dim=1536)
        call_count += 1
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
            "items": [{"question_type": "single_choice", "count": 3}],
            "difficulty": None,
        }
    )

    job = await _get_job(job_id)
    # 2 of 3 succeeded -> job still reaches "done", not "failed" (.rule:
    # 一題失敗不得整批重跑；job.error carries the failure summary instead).
    assert job.status == "done"
    assert job.progress == "3/3"
    assert job.error == "1 題出題失敗"

    questions = await _questions_for_type("single_choice")
    assert len(questions) == 2


async def test_all_generations_failing_marks_the_job_failed(monkeypatch) -> None:
    document_id = await _make_document()
    category_id = await _make_category()
    await _make_chunk(document_id=document_id, category_id=category_id, content="內容")

    def handler(request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content)
        if request.url.path == "/v1/embeddings":
            return _embeddings_response(model=body["model"], dim=1536)
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
            "items": [{"question_type": "single_choice", "count": 1}],
            "difficulty": None,
        }
    )

    job = await _get_job(job_id)
    assert job.status == "failed"
    assert job.error == "1 題出題失敗"

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
            "items": [{"question_type": "single_choice", "count": 2}],
            "difficulty": None,
        }
    )

    job = await _get_job(job_id)
    assert job.status == "failed"
    assert job.error == "單選題找不到可用素材"
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
            "items": [{"question_type": "essay", "count": 1}],
            "difficulty": None,
        }
    )

    job = await _get_job(job_id)
    assert job.status == "failed"
    assert job.error == "未知題型"
    assert captured == []


def test_find_banned_phrase_detects_source_referential_wording_in_any_field() -> None:
    """docs/question-bank.md 題幹自足原則 — the detector walks every
    user-visible text field generically (stem/options/explanation/answers/
    key_points/nested comparison fields), not a per-type field list."""
    cases: dict[str, dict[str, object]] = {
        "stem, 根據+教材": {"stem": "根據教材內容，光合作用發生在哪裡？", "options": ["a", "b"]},
        "explanation, 教材指出": {
            "stem": "光合作用發生在哪裡？",
            "explanation": "教材指出答案是葉綠體。",
        },
        "option text, 文中": {"stem": "何者正確？", "options": ["如文中所述的葉綠體", "b"]},
        "answers list, 課文提到": {"stem": "____ 是正確答案。", "answers": ["課文提到的答案"]},
        "key_points, 如上所述": {
            "stem": "說明光合作用。",
            "model_answer": "略。",
            "key_points": ["如上所述，發生在葉綠體"],
        },
        "nested comparison field, 依據本文": {
            "stem": "比較光合作用與呼吸作用。",
            "model_answer": {
                "similarities": [],
                "differences": [{"aspect": "場所", "a": "依據本文的葉綠體", "b": "粒線體"}],
            },
        },
    }
    for label, payload in cases.items():
        assert generation_module._find_banned_phrase(payload) is not None, label


def test_find_banned_phrase_does_not_flag_legitimate_quiz_text() -> None:
    """Patterns are anchored to source-words (教材/課文/本文/上文/內文) — bare
    根據 and bare 內容 must not match on their own."""
    cases: dict[str, dict[str, object]] = {
        "bare 內容, no source word": {"stem": "下列內容何者正確？", "options": ["a", "b"]},
        "根據 + a law, not a source word": {
            "stem": "根據牛頓第二定律，力等於質量乘以加速度，下列敘述何者正確？",
            "options": ["a", "b"],
        },
        "plain quiz text": {
            "stem": "在細胞的能量代謝反應中，光合作用發生於下列哪個構造？",
            "options": ["粒線體", "葉綠體"],
            "explanation": "葉綠體含有葉綠素，能吸收光能進行光合作用。",
        },
    }
    for label, payload in cases.items():
        assert generation_module._find_banned_phrase(payload) is None, label


def test_corrective_instruction_never_echoes_a_phrase_and_guards_against_meta_questions() -> None:
    """A live run showed the retry prompt quoting the offending phrase back
    (e.g. 「根據教材內容」) seeded a meta-question ABOUT the self-containment
    rule itself instead of a fresh question on the source material. The fix:
    the corrective instruction never echoes any banned phrase, explicitly
    asks for a brand-new question on the same subject matter, and tells the
    model the rules are meta-instructions to itself, not testable content."""
    instruction = generation_module._corrective_instruction()

    # Never quotes any of the concrete banned strings back at the model.
    assert generation_module._find_banned_phrase({"instruction": instruction}) is None
    for phrase in ["根據教材內容", "根據課文", "根據本文", "文中提到", "如上所述"]:
        assert phrase not in instruction

    # Explicitly asks for a new question on the same subject, not a
    # discussion of the rules.
    assert "重新出一題全新的題目" in instruction
    assert "不是教材要考的知識" in instruction


async def test_regeneration_recovers_from_a_banned_first_attempt(monkeypatch) -> None:
    """First response's stem names the source ("根據教材內容") -> triggers one
    regeneration with a corrective instruction naming the phrase; the retry
    is clean -> the question is inserted and both LLM calls are recorded."""
    document_id = await _make_document()
    category_id = await _make_category()
    await _make_chunk(document_id=document_id, category_id=category_id, content="第一段內容")

    call_count = 0

    def handler(request: httpx2.Request) -> httpx2.Response:
        nonlocal call_count
        body = json.loads(request.content)
        if request.url.path == "/v1/embeddings":
            return _embeddings_response(model=body["model"], dim=1536)
        call_count += 1
        if call_count == 1:
            banned = {
                **CANNED_PAYLOADS["SingleChoiceQuestion"],
                "stem": "根據教材內容，光合作用發生在細胞的哪個構造？",
            }
            return _chat_completion_response(model=body["model"], content=banned)
        # The retry prompt must carry the corrective instruction — but the
        # instruction itself must add no *extra* echo of the offending
        # phrase beyond whatever the base prompt's own bad/good example
        # already contains (a live run showed quoting the phrase a second
        # time, framed as "this is what you just violated", seeded a
        # meta-question about the rule itself) — and must tell the model to
        # write a brand-new question rather than discuss the rules.
        prompt_text = body["messages"][0]["content"]
        base_prompt_only = build_prompt("single_choice", ["第一段內容"], None)
        assert prompt_text.count("根據教材內容") == base_prompt_only.count("根據教材內容")
        assert "重新出一題全新的題目" in prompt_text
        assert "不是教材要考的知識" in prompt_text
        return _chat_completion_response(
            model=body["model"], content=CANNED_PAYLOADS["SingleChoiceQuestion"]
        )

    fake_client = _fake_llm_client(handler)
    monkeypatch.setattr(generation_module, "get_llm_client", lambda: fake_client)

    job_id = await _run_job(
        {
            "document_ids": [document_id],
            "category_ids": None,
            "items": [{"question_type": "single_choice", "count": 1}],
            "difficulty": None,
        }
    )

    job = await _get_job(job_id)
    assert job.status == "done"
    assert job.error is None
    assert call_count == 2

    questions = await _questions_for_type("single_choice")
    assert len(questions) == 1
    assert questions[0].payload["stem"] == CANNED_PAYLOADS["SingleChoiceQuestion"]["stem"]

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


async def test_question_fails_when_both_attempts_are_banned(monkeypatch) -> None:
    """Both the first attempt and the regeneration still name the source ->
    the question counts as failed (not inserted), the job's error summary
    names it, and sibling questions from other units are unaffected."""
    document_id = await _make_document()
    category_id = await _make_category()
    for i in range(3):
        await _make_chunk(document_id=document_id, category_id=category_id, content=f"內容{i}")

    def handler(request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content)
        if request.url.path == "/v1/embeddings":
            return _embeddings_response(model=body["model"], dim=1536)
        prompt_text = body["messages"][0]["content"]
        if "內容0" in prompt_text:
            banned = {
                **CANNED_PAYLOADS["SingleChoiceQuestion"],
                "stem": "根據教材內容，光合作用發生在細胞的哪個構造？",
            }
            return _chat_completion_response(model=body["model"], content=banned)
        return _chat_completion_response(
            model=body["model"], content=CANNED_PAYLOADS["SingleChoiceQuestion"]
        )

    fake_client = _fake_llm_client(handler)
    monkeypatch.setattr(generation_module, "get_llm_client", lambda: fake_client)

    job_id = await _run_job(
        {
            "document_ids": [document_id],
            "category_ids": None,
            "items": [{"question_type": "single_choice", "count": 3}],
            "difficulty": None,
        }
    )

    job = await _get_job(job_id)
    # 2 of 3 succeeded -> job still reaches "done"; the failure summary names
    # the reason class, not the exception or the banned phrase.
    assert job.status == "done"
    assert job.progress == "3/3"
    assert job.error == "1 題出題失敗（題幹引用教材）"

    questions = await _questions_for_type("single_choice")
    assert len(questions) == 2
    for question in questions:
        stem = question.payload["stem"]
        assert isinstance(stem, str)
        assert "根據教材內容" not in stem

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
    # chunk0's question retried once (2 calls) + the other 2 succeeded first try.
    assert len(usage_rows) == 4


async def test_multi_item_job_generates_every_combo_with_shared_progress_total(
    monkeypatch,
) -> None:
    """docs/question-bank.md 出題流程 step 1 — one job, multiple `{question_type,
    count}` combos; progress is the running total across every item."""
    document_id = await _make_document()
    category_id = await _make_category()
    for i in range(5):
        await _make_chunk(document_id=document_id, category_id=category_id, content=f"內容{i}")

    captured: list[httpx2.Request] = []
    fake_client = _fake_llm_client(_canned_handler(captured))
    monkeypatch.setattr(generation_module, "get_llm_client", lambda: fake_client)

    job_id = await _run_job(
        {
            "document_ids": [document_id],
            "category_ids": None,
            "items": [
                {"question_type": "single_choice", "count": 2},
                {"question_type": "true_false", "count": 1},
                {"question_type": "short_answer", "count": 1},
            ],
            "difficulty": None,
        }
    )

    job = await _get_job(job_id)
    assert job.status == "done"
    assert job.progress == "4/4"
    assert job.error is None

    assert len(await _questions_for_type("single_choice")) == 2
    assert len(await _questions_for_type("true_false")) == 1
    assert len(await _questions_for_type("short_answer")) == 1

    schema_names = [
        json.loads(request.content)["response_format"]["json_schema"]["name"]
        for request in captured
    ]
    assert schema_names.count("SingleChoiceQuestion") == 2
    assert schema_names.count("TrueFalseQuestion") == 1
    assert schema_names.count("ShortAnswerQuestion") == 1


async def test_one_item_with_no_eligible_material_does_not_abort_the_other_items(
    monkeypatch,
) -> None:
    """The failing item (`comparison` — no embedded chunks exist, so there are
    no candidate pairs) must not stop the other item (`single_choice`) from
    generating, and the job still ends `done` with a note about the failed
    item (docs/question-bank.md — 單一項目全失敗不影響其他項目)."""
    document_id = await _make_document()
    category_id = await _make_category()
    await _make_chunk(document_id=document_id, category_id=category_id, content="內容")

    captured: list[httpx2.Request] = []
    fake_client = _fake_llm_client(_canned_handler(captured))
    monkeypatch.setattr(generation_module, "get_llm_client", lambda: fake_client)

    job_id = await _run_job(
        {
            "document_ids": [document_id],
            "category_ids": None,
            "items": [
                {"question_type": "comparison", "count": 1},
                {"question_type": "single_choice", "count": 1},
            ],
            "difficulty": None,
        }
    )

    job = await _get_job(job_id)
    assert job.status == "done"
    assert job.progress == "1/1"
    assert job.error == "比較題找不到可用素材"

    assert len(await _questions_for_type("comparison")) == 0
    assert len(await _questions_for_type("single_choice")) == 1


async def test_all_items_with_no_eligible_material_marks_the_job_failed(monkeypatch) -> None:
    document_id = await _make_document()  # no chunks at all

    captured: list[httpx2.Request] = []
    fake_client = _fake_llm_client(_canned_handler(captured))
    monkeypatch.setattr(generation_module, "get_llm_client", lambda: fake_client)

    job_id = await _run_job(
        {
            "document_ids": [document_id],
            "category_ids": None,
            "items": [
                {"question_type": "single_choice", "count": 1},
                {"question_type": "true_false", "count": 1},
            ],
            "difficulty": None,
        }
    )

    job = await _get_job(job_id)
    assert job.status == "failed"
    assert job.error == "單選題找不到可用素材；是非題找不到可用素材"
    assert captured == []
