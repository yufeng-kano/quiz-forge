"""Real-Postgres tests for the pg-as-queue job framework (`backend.jobs`).

Exercises `claim_job` (SKIP LOCKED concurrency), `JobContext.set_progress`,
failure handling, stale-running requeue, and a full `JobWorkerPool` run —
against a real database, no mocking of the queue logic itself.
"""

import asyncio

import pytest
from factories import create_job

from backend.db.session import AsyncSessionLocal
from backend.jobs.context import JobContext
from backend.jobs.registry import register_handler
from backend.jobs.service import JobWorkerPool
from backend.jobs.worker import claim_job, reset_stale_running_jobs, run_claimed_job
from backend.models.job import Job


async def test_claim_job_returns_none_when_queue_empty() -> None:
    async with AsyncSessionLocal() as session:
        claimed = await claim_job(session)
    assert claimed is None


async def test_claim_job_marks_running_and_clears_error() -> None:
    job_id = await create_job("test_queue_noop", error="stale error from a previous run")

    async with AsyncSessionLocal() as session:
        job = await claim_job(session)

    assert job is not None
    assert job.id == job_id
    assert job.status == "running"
    assert job.error is None


async def test_claim_job_skip_locked_no_double_claim() -> None:
    """Two workers polling at the same moment must each get a distinct job."""
    job_ids = {await create_job("test_queue_noop") for _ in range(3)}

    async def _claim() -> Job | None:
        async with AsyncSessionLocal() as session:
            return await claim_job(session)

    claimed = await asyncio.gather(_claim(), _claim(), _claim())
    assert all(job is not None for job in claimed)
    claimed_ids = {job.id for job in claimed if job is not None}

    assert claimed_ids == job_ids, "every pending job should be claimed exactly once"
    assert all(job.status == "running" for job in claimed if job is not None)


async def test_job_context_set_progress_persists() -> None:
    job_id = await create_job("test_queue_noop")

    async with AsyncSessionLocal() as session:
        job = await claim_job(session)
        assert job is not None
        ctx = JobContext(job=job, session=session)
        await ctx.set_progress("3/10")

    async with AsyncSessionLocal() as session:
        fetched = await session.get(Job, job_id)
        assert fetched is not None
        assert fetched.progress == "3/10"


@register_handler("test_queue_success")
async def _success_handler(ctx: JobContext) -> None:
    await ctx.set_progress("1/2")
    await ctx.set_progress("2/2")


async def test_run_claimed_job_success_marks_done_and_keeps_progress() -> None:
    job_id = await create_job("test_queue_success")
    async with AsyncSessionLocal() as session:
        claimed = await claim_job(session)
        assert claimed is not None

    await run_claimed_job(AsyncSessionLocal, job_id)

    async with AsyncSessionLocal() as session:
        fetched = await session.get(Job, job_id)
        assert fetched is not None
        assert fetched.status == "done"
        assert fetched.progress == "2/2"
        assert fetched.error is None


@register_handler("test_queue_fail")
async def _failing_handler(ctx: JobContext) -> None:
    await ctx.set_progress("1/3")
    raise ValueError("synthetic failure for test")


async def test_run_claimed_job_failure_writes_error_not_retry_count() -> None:
    job_id = await create_job("test_queue_fail")
    async with AsyncSessionLocal() as session:
        claimed = await claim_job(session)
        assert claimed is not None

    await run_claimed_job(AsyncSessionLocal, job_id)

    async with AsyncSessionLocal() as session:
        fetched = await session.get(Job, job_id)
        assert fetched is not None
        assert fetched.status == "failed"
        assert fetched.error is not None
        assert "synthetic failure for test" in fetched.error
        # retry_count only moves when a human/API retries the job (see
        # POST /v1/jobs/{id}/retry) — a bare failure does not bump it.
        assert fetched.retry_count == 0


async def test_run_claimed_job_unknown_kind_fails_with_message() -> None:
    job_id = await create_job("test_queue_no_such_handler_registered")
    async with AsyncSessionLocal() as session:
        claimed = await claim_job(session)
        assert claimed is not None

    await run_claimed_job(AsyncSessionLocal, job_id)

    async with AsyncSessionLocal() as session:
        fetched = await session.get(Job, job_id)
        assert fetched is not None
        assert fetched.status == "failed"
        assert fetched.error is not None
        assert "no handler registered" in fetched.error


async def test_reset_stale_running_jobs_requeues_only_running_rows() -> None:
    stale_id = await create_job("test_queue_noop", status="running")
    pending_id = await create_job("test_queue_noop", status="pending")
    done_id = await create_job("test_queue_noop", status="done")

    requeued_count = await reset_stale_running_jobs(AsyncSessionLocal)
    assert requeued_count == 1

    async with AsyncSessionLocal() as session:
        stale = await session.get(Job, stale_id)
        pending = await session.get(Job, pending_id)
        done = await session.get(Job, done_id)
        assert stale is not None and stale.status == "pending"
        assert pending is not None and pending.status == "pending"
        assert done is not None and done.status == "done"


async def test_job_worker_pool_end_to_end_processes_pending_job() -> None:
    """Full loop, no shortcuts: pool claims a pending job unattended and finishes it."""
    job_id = await create_job("test_queue_success")

    pool = JobWorkerPool(
        session_factory=AsyncSessionLocal, worker_count=1, poll_interval_seconds=0.05
    )
    await pool.start()
    try:
        final_status: str | None = None
        for _ in range(100):
            async with AsyncSessionLocal() as session:
                job = await session.get(Job, job_id)
            assert job is not None
            final_status = job.status
            if final_status == "done":
                break
            await asyncio.sleep(0.05)
        else:
            pytest.fail(f"job did not reach 'done' within timeout (last status: {final_status})")
    finally:
        await pool.stop()

    async with AsyncSessionLocal() as session:
        final = await session.get(Job, job_id)
        assert final is not None
        assert final.status == "done"
        assert final.progress == "2/2"
