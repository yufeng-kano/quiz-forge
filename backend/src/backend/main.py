"""FastAPI application entrypoint."""

from fastapi import FastAPI

from backend.api.v1 import router as v1_router

app = FastAPI(title="QuizForge API")
app.include_router(v1_router)
