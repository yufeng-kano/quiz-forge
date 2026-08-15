"""Liveness endpoint."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def get_health() -> dict[str, str]:
    """Liveness check for nginx/monitoring — exposed publicly as `/api/v1/health`."""
    return {"status": "ok"}
