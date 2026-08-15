"""Internal `/v1` router, published by nginx as `/api/v1/*`."""

from fastapi import APIRouter

from backend.api.v1 import (
    assets,
    categories,
    documents,
    exports,
    generate,
    health,
    jobs,
    pages,
    questions,
    stats,
    usage,
)

router = APIRouter(prefix="/v1")
router.include_router(health.router)
router.include_router(jobs.router)
router.include_router(usage.router)
router.include_router(stats.router)
router.include_router(documents.router)
router.include_router(pages.router)
router.include_router(assets.router)
router.include_router(categories.router)
router.include_router(generate.router)
router.include_router(questions.router)
router.include_router(exports.router)
