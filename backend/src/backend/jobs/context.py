"""Per-job execution context handed to job handlers.

Wraps the claimed `Job` row and the `AsyncSession` that owns its transaction
so a handler can report incremental progress (e.g. "12/40" pages) without
knowing anything about how the queue claims or dispatches work.
"""

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.job import Job


@dataclass
class JobContext:
    job: Job
    session: AsyncSession

    @property
    def job_id(self) -> int:
        return self.job.id

    @property
    def kind(self) -> str:
        return self.job.kind

    @property
    def payload(self) -> dict[str, object]:
        return self.job.payload

    async def set_progress(self, progress: str) -> None:
        """Update `jobs.progress` and commit immediately.

        Handlers call this after each unit of work (page, question, ...) so
        `GET /v1/jobs/{id}` reflects live progress while the job still runs.
        """
        self.job.progress = progress
        await self.session.commit()
