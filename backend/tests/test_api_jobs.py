"""`GET /v1/jobs`, `GET /v1/jobs/{id}` and `POST /v1/jobs/{id}/retry` through
the real HTTP app."""

from factories import create_job
from fastapi.testclient import TestClient


async def test_get_job_returns_status_and_progress(client: TestClient) -> None:
    job_id = await create_job("test_api_kind", status="running", progress="4/10")

    response = client.get(f"/v1/jobs/{job_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == job_id
    assert body["kind"] == "test_api_kind"
    assert body["status"] == "running"
    assert body["progress"] == "4/10"
    assert body["error"] is None
    assert body["retry_count"] == 0


def test_get_job_404_for_missing_job(client: TestClient) -> None:
    response = client.get("/v1/jobs/999999999")
    assert response.status_code == 404


async def test_retry_resets_failed_job_to_pending_and_bumps_retry_count(
    client: TestClient,
) -> None:
    job_id = await create_job(
        "test_api_kind", status="failed", error="boom", retry_count=1, progress="2/5"
    )

    response = client.post(f"/v1/jobs/{job_id}/retry")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "pending"
    assert body["error"] is None
    assert body["retry_count"] == 2

    follow_up = client.get(f"/v1/jobs/{job_id}")
    assert follow_up.json()["status"] == "pending"


async def test_retry_rejects_running_job_with_409(client: TestClient) -> None:
    job_id = await create_job("test_api_kind", status="running")

    response = client.post(f"/v1/jobs/{job_id}/retry")

    assert response.status_code == 409


async def test_retry_rejects_pending_job_with_409(client: TestClient) -> None:
    job_id = await create_job("test_api_kind", status="pending")

    response = client.post(f"/v1/jobs/{job_id}/retry")

    assert response.status_code == 409


def test_retry_404_for_missing_job(client: TestClient) -> None:
    response = client.post("/v1/jobs/999999999/retry")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /v1/jobs (F5)
# ---------------------------------------------------------------------------


async def test_list_jobs_newest_first(client: TestClient) -> None:
    first_id = await create_job("test_list_kind")
    second_id = await create_job("test_list_kind")

    response = client.get("/v1/jobs")

    assert response.status_code == 200
    ids = [item["id"] for item in response.json()]
    assert ids.index(second_id) < ids.index(first_id)


async def test_list_jobs_filters_by_status(client: TestClient) -> None:
    pending_id = await create_job("test_list_kind", status="pending")
    await create_job("test_list_kind", status="done")

    response = client.get("/v1/jobs", params={"status": "pending"})

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [pending_id]


async def test_list_jobs_filters_by_kind(client: TestClient) -> None:
    export_id = await create_job("export_docx")
    await create_job("generate_questions")

    response = client.get("/v1/jobs", params={"kind": "export_docx"})

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [export_id]


async def test_list_jobs_respects_limit(client: TestClient) -> None:
    for _ in range(3):
        await create_job("test_list_kind")

    response = client.get("/v1/jobs", params={"limit": 2})

    assert response.status_code == 200
    assert len(response.json()) == 2


def test_list_jobs_rejects_limit_above_settings_max(client: TestClient) -> None:
    response = client.get("/v1/jobs", params={"limit": 999999})
    assert response.status_code == 422
