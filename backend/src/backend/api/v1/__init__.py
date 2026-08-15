"""Internal `/v1` router, published by nginx as `/api/v1/*`."""

from fastapi import APIRouter

from backend.api.v1 import health, jobs, usage

router = APIRouter(prefix="/v1")
router.include_router(health.router)
router.include_router(jobs.router)
router.include_router(usage.router)
