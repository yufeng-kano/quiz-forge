"""`GET /v1/health` — smoke test for the FastAPI skeleton."""

from fastapi.testclient import TestClient

from backend.main import app


def test_health() -> None:
    with TestClient(app) as client:
        response = client.get("/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
