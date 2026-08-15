"""`GET /v1/usage` — aggregate token totals grouped by model and by purpose."""

from factories import create_llm_usage
from fastapi.testclient import TestClient


async def test_usage_aggregates_by_model_and_purpose(client: TestClient) -> None:
    await create_llm_usage(
        model="openai/gpt-5.6-luna", purpose="generate_questions",
        prompt_tokens=100, completion_tokens=50,
    )
    await create_llm_usage(
        model="openai/gpt-5.6-luna", purpose="generate_questions",
        prompt_tokens=200, completion_tokens=80,
    )
    await create_llm_usage(
        model="google/gemini-3.6-flash", purpose="parse_document",
        prompt_tokens=1000, completion_tokens=300,
    )

    response = client.get("/v1/usage")

    assert response.status_code == 200
    body = response.json()

    assert body["total"] == {
        "prompt_tokens": 1300,
        "completion_tokens": 430,
        "total_tokens": 1730,
        "call_count": 3,
    }

    by_model = {row["model"]: row for row in body["by_model"]}
    assert by_model["openai/gpt-5.6-luna"] == {
        "model": "openai/gpt-5.6-luna",
        "prompt_tokens": 300,
        "completion_tokens": 130,
        "total_tokens": 430,
        "call_count": 2,
    }
    assert by_model["google/gemini-3.6-flash"]["call_count"] == 1

    by_purpose = {row["purpose"]: row for row in body["by_purpose"]}
    assert by_purpose["generate_questions"]["total_tokens"] == 430
    assert by_purpose["parse_document"]["total_tokens"] == 1300


def test_usage_empty_when_no_calls_yet(client: TestClient) -> None:
    response = client.get("/v1/usage")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "call_count": 0,
    }
    assert body["by_model"] == []
    assert body["by_purpose"] == []
