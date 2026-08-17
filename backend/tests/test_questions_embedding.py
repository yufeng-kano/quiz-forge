"""`backend.questions.embedding` — payload-to-text flattening and the
`embed_questions` job handler (.rule 反偷懶規則: job queue 屬高風險邏輯，須有
測試). The LLM transport is faked exactly like `test_questions_generation.py`
(`httpx2.MockTransport`, `openai` talks over `httpx2` not `httpx`) so only the
network call is mocked — job/batching/failure-isolation logic under test is
never mocked away.
"""

import json
from collections.abc import Callable

import httpx2
import openai
import pytest
from factories import create_job
from pydantic import ValidationError

import backend.questions.embedding as embedding_module
from backend.core.config import Settings, get_settings
from backend.db.session import AsyncSessionLocal
from backend.jobs.worker import claim_job, run_claimed_job
from backend.llm.client import LLMClient
from backend.models.job import Job
from backend.models.question import Question
from backend.questions.embedding import flatten_question_payload

# ---------------------------------------------------------------------------
# flatten_question_payload -- payload-to-text coverage for all six types
# (docs/question-bank.md 題目向量化與語意搜尋)
# ---------------------------------------------------------------------------


def test_flatten_comparison_includes_subjects_aspects_and_differences() -> None:
    text = flatten_question_payload(
        "comparison",
        {
            "stem": "試比較光合作用與呼吸作用之異同。",
            "subject_a": "光合作用",
            "subject_b": "呼吸作用",
            "aspects": ["場所", "能量轉換"],
            "model_answer": {
                "similarities": ["皆為細胞內能量代謝反應"],
                "differences": [{"aspect": "場所", "a": "葉綠體", "b": "粒線體"}],
            },
        },
    )
    for token in [
        "試比較光合作用與呼吸作用之異同",
        "光合作用",
        "呼吸作用",
        "場所",
        "能量轉換",
        "皆為細胞內能量代謝反應",
        "葉綠體",
        "粒線體",
    ]:
        assert token in text, text


def test_flatten_analogy_includes_all_four_slots_and_options_and_explanation() -> None:
    text = flatten_question_payload(
        "analogy",
        {
            "a": "筆",
            "b": "寫字",
            "c": "剪刀",
            "answer": "剪裁",
            "options": ["剪裁", "縫紉", "烹飪", "測量"],
            "explanation": "工具之於其功能",
        },
    )
    for token in ["筆", "寫字", "剪刀", "剪裁", "縫紉", "烹飪", "測量", "工具之於其功能"]:
        assert token in text, text


def test_flatten_analogy_without_options_still_covers_all_four_slots() -> None:
    text = flatten_question_payload(
        "analogy",
        {
            "a": "筆",
            "b": "寫字",
            "c": "剪刀",
            "answer": "剪裁",
            "options": None,
            "explanation": None,
        },
    )
    for token in ["筆", "寫字", "剪刀", "剪裁"]:
        assert token in text, text


def test_flatten_single_choice_includes_stem_options_answer_text_and_explanation() -> None:
    text = flatten_question_payload(
        "single_choice",
        {
            "stem": "光合作用發生在細胞的哪個構造？",
            "options": ["粒線體", "葉綠體", "細胞核", "核糖體"],
            "answer_index": 1,
            "explanation": "葉綠體含有葉綠素，能吸收光能。",
        },
    )
    assert "光合作用發生在細胞的哪個構造" in text
    for option in ["粒線體", "葉綠體", "細胞核", "核糖體"]:
        assert option in text
    assert "葉綠體含有葉綠素" in text
    # The correct answer's actual text (not just its index) must be present.
    assert "答案：葉綠體" in text


def test_flatten_true_false_uses_human_readable_answer_and_includes_explanation() -> None:
    text_true = flatten_question_payload(
        "true_false",
        {"stem": "光合作用會釋放氧氣。", "answer": True, "explanation": "光合作用產物之一是氧氣。"},
    )
    assert "光合作用會釋放氧氣" in text_true
    assert "正確" in text_true
    assert "光合作用產物之一是氧氣" in text_true

    text_false = flatten_question_payload(
        "true_false", {"stem": "地球是平的。", "answer": False, "explanation": None}
    )
    assert "地球是平的" in text_false
    assert "錯誤" in text_false


def test_flatten_fill_blank_includes_stem_and_every_answer_in_order() -> None:
    text = flatten_question_payload(
        "fill_blank",
        {"stem": "水的化學式為 ____，由 ____ 與氧組成。", "answers": ["H2O", "氫"]},
    )
    assert "水的化學式為" in text
    assert "H2O" in text
    assert "氫" in text


def test_flatten_short_answer_includes_stem_model_answer_and_every_key_point() -> None:
    text = flatten_question_payload(
        "short_answer",
        {
            "stem": "請說明光合作用的功能。",
            "model_answer": "將光能轉換成化學能。",
            "key_points": ["光能轉化學能", "發生在葉綠體"],
        },
    )
    assert "請說明光合作用的功能" in text
    assert "將光能轉換成化學能" in text
    assert "光能轉化學能" in text
    assert "發生在葉綠體" in text


def test_flatten_revalidates_payload_and_raises_on_shape_violation() -> None:
    """`flatten_question_payload` re-validates through `parse_question` --
    the exact discriminated-union validation every other write path uses --
    rather than trusting a stored payload blindly."""
    with pytest.raises(ValidationError):
        flatten_question_payload(
            "single_choice",
            {"stem": "...", "options": ["only-one"], "answer_index": 0},
        )


# ---------------------------------------------------------------------------
# `embed_questions` job handler
# ---------------------------------------------------------------------------


def _embeddings_response(*, model: str, count: int, dim: int) -> httpx2.Response:
    return httpx2.Response(
        200,
        json={
            "object": "list",
            "model": model,
            "data": [
                {"object": "embedding", "index": i, "embedding": [0.0] * dim}
                for i in range(count)
            ],
            "usage": {"prompt_tokens": 2, "total_tokens": 2},
        },
    )


def _canned_embed_handler(dim: int = 1536) -> Callable[[httpx2.Request], httpx2.Response]:
    def handler(request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content)
        texts = body["input"]
        count = len(texts) if isinstance(texts, list) else 1
        return _embeddings_response(model=body["model"], count=count, dim=dim)

    return handler


def _fake_llm_client(handler: Callable[[httpx2.Request], httpx2.Response]) -> LLMClient:
    settings = Settings(llm_base_url="https://llm.test/v1", llm_api_key="test-key-not-real")
    fake_openai_client = openai.AsyncOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler)),
    )
    return LLMClient(
        settings=settings, session_factory=AsyncSessionLocal, openai_client=fake_openai_client
    )


def _single_choice_payload(stem: str = "...") -> dict[str, object]:
    return {
        "stem": stem,
        "options": ["a", "b", "c", "d"],
        "answer_index": 0,
        "explanation": None,
    }


async def _make_question(
    *, embedding: list[float] | None = None, payload: dict[str, object] | None = None
) -> int:
    async with AsyncSessionLocal() as session:
        question = Question(
            type="single_choice",
            status="draft",
            payload=payload or _single_choice_payload(),
            source_chunk_ids=[],
            embedding=embedding,
        )
        session.add(question)
        await session.commit()
        await session.refresh(question)
        return question.id


async def _get_question(question_id: int) -> Question:
    async with AsyncSessionLocal() as session:
        question = await session.get(Question, question_id)
        assert question is not None
        return question


async def _run_embed_job(payload: dict[str, object]) -> int:
    job_id = await create_job("embed_questions", payload=payload)
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


async def test_null_question_ids_backfills_every_null_embedding_question(monkeypatch) -> None:
    already_embedded = [0.25] * Settings().embedding_dim
    q1 = await _make_question(embedding=None)
    q2 = await _make_question(embedding=None)
    q3 = await _make_question(embedding=already_embedded)  # must be left untouched

    fake_client = _fake_llm_client(_canned_embed_handler())
    monkeypatch.setattr(embedding_module, "get_llm_client", lambda: fake_client)

    job_id = await _run_embed_job({"question_ids": None})

    job = await _get_job(job_id)
    assert job.status == "done"
    assert job.progress == "2/2"
    assert job.error is None

    assert (await _get_question(q1)).embedding is not None
    assert (await _get_question(q2)).embedding is not None
    assert (await _get_question(q3)).embedding == pytest.approx(already_embedded)


async def test_explicit_question_ids_reembeds_regardless_of_current_embedding(
    monkeypatch,
) -> None:
    """An explicit id list re-embeds even a question that already has a
    (stale) embedding -- this is exactly how `PATCH /v1/questions/{id}`
    picks up a fresh vector after nulling the old one out."""
    stale = [0.9] * Settings().embedding_dim
    question_id = await _make_question(embedding=stale)

    fake_client = _fake_llm_client(_canned_embed_handler())
    monkeypatch.setattr(embedding_module, "get_llm_client", lambda: fake_client)

    job_id = await _run_embed_job({"question_ids": [question_id]})

    job = await _get_job(job_id)
    assert job.status == "done"
    assert job.progress == "1/1"

    updated = await _get_question(question_id)
    assert updated.embedding is not None
    assert updated.embedding != pytest.approx(stale)


async def test_empty_explicit_question_ids_is_a_noop(monkeypatch) -> None:
    fake_client = _fake_llm_client(_canned_embed_handler())
    monkeypatch.setattr(embedding_module, "get_llm_client", lambda: fake_client)

    job_id = await _run_embed_job({"question_ids": []})

    job = await _get_job(job_id)
    assert job.status == "done"
    assert job.progress == "0/0"
    assert job.error is None


async def test_null_question_ids_with_nothing_pending_is_a_noop(monkeypatch) -> None:
    await _make_question(embedding=[0.1] * Settings().embedding_dim)  # already embedded

    fake_client = _fake_llm_client(_canned_embed_handler())
    monkeypatch.setattr(embedding_module, "get_llm_client", lambda: fake_client)

    job_id = await _run_embed_job({"question_ids": None})

    job = await _get_job(job_id)
    assert job.status == "done"
    assert job.progress == "0/0"
    assert job.error is None


async def test_missing_question_id_fails_only_that_item(monkeypatch) -> None:
    question_id = await _make_question(embedding=None)

    fake_client = _fake_llm_client(_canned_embed_handler())
    monkeypatch.setattr(embedding_module, "get_llm_client", lambda: fake_client)

    job_id = await _run_embed_job({"question_ids": [question_id, 999999999]})

    job = await _get_job(job_id)
    assert job.status == "done"
    assert job.progress == "2/2"
    assert job.error == "1 題向量化失敗（題目不存在）"

    assert (await _get_question(question_id)).embedding is not None


async def test_unparsable_payload_fails_only_that_item(monkeypatch) -> None:
    """A stored payload that no longer validates (e.g. `single_choice` with a
    single option) fails to flatten -- that question alone is skipped, the
    rest of the batch still embeds (.rule 反偷懶規則 禁止部分處理／最小單位可
    重試)."""
    broken_id = await _make_question(
        embedding=None,
        payload={"stem": "...", "options": ["only-one"], "answer_index": 0},
    )
    good_id = await _make_question(embedding=None)

    fake_client = _fake_llm_client(_canned_embed_handler())
    monkeypatch.setattr(embedding_module, "get_llm_client", lambda: fake_client)

    job_id = await _run_embed_job({"question_ids": [broken_id, good_id]})

    job = await _get_job(job_id)
    assert job.status == "done"
    assert job.progress == "2/2"
    assert job.error == "1 題向量化失敗（題目內容無法向量化）"

    assert (await _get_question(broken_id)).embedding is None
    assert (await _get_question(good_id)).embedding is not None


async def test_all_targeted_questions_failing_marks_the_job_failed(monkeypatch) -> None:
    broken_id = await _make_question(
        embedding=None,
        payload={"stem": "...", "options": ["only-one"], "answer_index": 0},
    )

    fake_client = _fake_llm_client(_canned_embed_handler())
    monkeypatch.setattr(embedding_module, "get_llm_client", lambda: fake_client)

    job_id = await _run_embed_job({"question_ids": [broken_id]})

    job = await _get_job(job_id)
    assert job.status == "failed"
    assert job.error == "1 題向量化失敗（題目內容無法向量化）"
    assert (await _get_question(broken_id)).embedding is None


async def test_batching_respects_question_embed_batch_size_and_embeds_everything(
    monkeypatch,
) -> None:
    monkeypatch.setenv("QUESTION_EMBED_BATCH_SIZE", "2")
    get_settings.cache_clear()
    try:
        question_ids = [await _make_question(embedding=None) for _ in range(5)]

        request_batch_sizes: list[int] = []

        def handler(request: httpx2.Request) -> httpx2.Response:
            body = json.loads(request.content)
            texts = body["input"]
            request_batch_sizes.append(len(texts))
            return _embeddings_response(model=body["model"], count=len(texts), dim=1536)

        fake_client = _fake_llm_client(handler)
        monkeypatch.setattr(embedding_module, "get_llm_client", lambda: fake_client)

        job_id = await _run_embed_job({"question_ids": None})

        job = await _get_job(job_id)
        assert job.status == "done"
        assert job.progress == "5/5"
        assert job.error is None
        # 5 questions at batch size 2 -> batches of [2, 2, 1].
        assert request_batch_sizes == [2, 2, 1]

        for question_id in question_ids:
            assert (await _get_question(question_id)).embedding is not None
    finally:
        get_settings.cache_clear()


async def test_one_failing_batch_does_not_abort_other_batches(monkeypatch) -> None:
    """A whole batch's embedding call erroring (e.g. a transient API error)
    fails every question in *that* batch without aborting any other batch."""
    monkeypatch.setenv("QUESTION_EMBED_BATCH_SIZE", "1")
    get_settings.cache_clear()
    try:
        question_ids = [await _make_question(embedding=None) for _ in range(3)]

        call_count = 0

        def handler(request: httpx2.Request) -> httpx2.Response:
            nonlocal call_count
            call_count += 1
            body = json.loads(request.content)
            if call_count == 2:
                # 400 (not 5xx) -- the openai SDK's default retry behaviour
                # only retries transient/5xx errors, so this fails
                # deterministically on the first attempt instead of quietly
                # succeeding on an automatic retry.
                return httpx2.Response(400, json={"error": {"message": "boom"}})
            texts = body["input"]
            return _embeddings_response(model=body["model"], count=len(texts), dim=1536)

        fake_client = _fake_llm_client(handler)
        monkeypatch.setattr(embedding_module, "get_llm_client", lambda: fake_client)

        job_id = await _run_embed_job({"question_ids": question_ids})

        job = await _get_job(job_id)
        assert job.status == "done"
        assert job.progress == "3/3"
        assert job.error == "1 題向量化失敗"

        embedded = [
            question_id
            for question_id in question_ids
            if (await _get_question(question_id)).embedding is not None
        ]
        assert len(embedded) == 2
    finally:
        get_settings.cache_clear()


async def test_malformed_question_ids_payload_marks_job_failed(monkeypatch) -> None:
    fake_client = _fake_llm_client(_canned_embed_handler())
    monkeypatch.setattr(embedding_module, "get_llm_client", lambda: fake_client)

    job_id = await _run_embed_job({"question_ids": "not-a-list"})

    job = await _get_job(job_id)
    assert job.status == "failed"
    assert job.error == "任務失敗"
