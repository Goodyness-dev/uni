"""Asynchronous background job queue, task execution harness, and worker runner."""
import asyncio
import traceback
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine, Dict, Optional
from sqlalchemy import select
from app.core.logging import job_id_ctx, logger
from app.db.base import AsyncSessionLocal
from app.db.models import Job

# Handler registry mapping job_type -> async handler function(job, payload, db_session)
JobHandler = Callable[[Job, Dict[str, Any], Any], Coroutine[Any, Any, Dict[str, Any]]]
_JOB_HANDLERS: Dict[str, JobHandler] = {}

MAX_JOB_ATTEMPTS = 3


def register_job_handler(job_type: str):
    """Decorator registering an asynchronous handler for a job type."""
    def decorator(fn: JobHandler) -> JobHandler:
        _JOB_HANDLERS[job_type] = fn
        return fn
    return decorator


async def enqueue_job(
    job_type: str,
    payload: Dict[str, Any],
    scheduled_for: Optional[datetime] = None,
) -> Job:
    """Enqueues a background job in the database."""
    async with AsyncSessionLocal() as session:
        job = Job(
            type=job_type,
            status="pending",
            attempts=0,
            scheduled_for=scheduled_for,
            last_error=None,
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)

        logger.info(f"Enqueued job {job.id} of type '{job_type}'")
        return job


async def execute_job(job_id: uuid.UUID, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Picks up and executes a single background job with retries and dead-letter handling."""
    job_id_ctx.set(str(job_id))

    async with AsyncSessionLocal() as session:
        job = await session.get(Job, job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found.")

        handler = _JOB_HANDLERS.get(job.type)
        if not handler:
            job.status = "dead_letter"
            job.last_error = f"No handler registered for job type '{job.type}'"
            await session.commit()
            raise NotImplementedError(job.last_error)

        job.status = "running"
        job.attempts += 1
        job.locked_by = f"worker_{uuid.uuid4().hex[:8]}"
        await session.commit()

        try:
            # Execute registered agent job handler
            result = await handler(job, payload, session)

            job.status = "completed"
            job.locked_by = None
            job.last_error = None
            await session.commit()
            logger.info(f"Job {job.id} ({job.type}) completed successfully.")
            return result

        except Exception as exc:
            err_msg = f"{type(exc).__name__}: {str(exc)}\n{traceback.format_exc()}"
            logger.error(f"Job {job.id} failed on attempt {job.attempts}: {err_msg}")

            if job.attempts >= MAX_JOB_ATTEMPTS:
                job.status = "dead_letter"
                logger.critical(f"Job {job.id} reached MAX_JOB_ATTEMPTS ({MAX_JOB_ATTEMPTS}). Moved to dead_letter.")
            else:
                job.status = "failed"

            job.last_error = err_msg
            job.locked_by = None
            await session.commit()
            raise
