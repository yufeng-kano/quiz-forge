"""`GET /v1/jobs/{id}` and `POST /v1/jobs/{id}/retry` through the real HTTP app."""

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
