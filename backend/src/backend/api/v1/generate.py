"""`POST /v1/generate` — enqueue a `generate_questions` job
(docs/question-bank.md 出題流程 step 1).

Only creates the `jobs` row; material selection and every LLM call happen in
the background worker (`backend.questions.generation`), per .rule 使用者體驗規則
(長任務一律走背景 job，前端輪詢 `/api/v1/jobs/{id}`)."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_session
from backend.models.job import Job
from backend.schemas.question import GenerateIn, GenerateOut

router = APIRouter(prefix="/generate", tags=["generation"])


@router.post("", response_model=GenerateOut, status_code=status.HTTP_201_CREATED)
async def create_generation_job(
    body: GenerateIn, session: AsyncSession = Depends(get_session)
) -> GenerateOut:
    job = Job(
        kind="generate_questions",
        payload={
            "document_ids": body.document_ids,
            "category_ids": body.category_ids,
            "items": [item.model_dump() for item in body.items],
            "difficulty": body.difficulty,
        },
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return GenerateOut(job_id=job.id)
