"""Internal `/v1` router, published by nginx as `/api/v1/*`."""

from fastapi import APIRouter

from backend.api.v1 import health

router = APIRouter(prefix="/v1")
router.include_router(health.router)
