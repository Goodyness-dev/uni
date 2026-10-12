"""Asynchronous background job queue, task execution harness, Redis broker, and worker runner."""
import asyncio
import json
import traceback
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Coroutine, Dict, Optional, List
from sqlalchemy import select, and_, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.logging import job_id_ctx, logger
from app.db.base import AsyncSessionLocal
from app.db.models import Job
from app.core.tracing import recovery_decision

# Handler registry mapping job_type -> async handler function(job, payload, db_session)
JobHandler = Callable[[Job, Dict[str, Any], Any], Coroutine[Any, Any, Dict[str, Any]]]
_JOB_HANDLERS: Dict[str, JobHandler] = {}

MAX_JOB_ATTEMPTS = 3
REDIS_QUEUE_KEY = "scholarpilot:jobs:queue"
REDIS_DEAD_LETTER_KEY = "scholarpilot:jobs:dead_letter"

_redis_client = None


async def get_redis_client():
    """Lazily gets or connects to Redis client with graceful fallback."""
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    try:
        import redis.asyncio as aioredis
        client = aioredis.from_url(
            settings.REDIS_URL,
            socket_connect_timeout=1.0,
            decode_responses=True,
        )
        await client.ping()
        _redis_client = client
        logger.info(f"Connected to Redis broker at {settings.REDIS_URL}")
        return _redis_client
    except Exception:
        # Fall back gracefully to database-backed queue
        return None


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
    session: Optional[AsyncSession] = None,
) -> Job:
    """Enqueues a background job in the database and dispatches to Redis task broker if available."""
    async def _insert(sess: AsyncSession) -> Job:
        job = Job(
            type=job_type,
            status="pending",
            payload=payload or {},
            attempts=0,
            scheduled_for=scheduled_for,
            last_error=None,
        )
        sess.add(job)
        await sess.commit()
        await sess.refresh(job)
        return job

    if session is not None:
        job = await _insert(session)
    else:
        async with AsyncSessionLocal() as sess:
            job = await _insert(sess)

    # Notify / enqueue to Redis broker if available
    redis_client = await get_redis_client()
    if redis_client:
        try:
            await redis_client.rpush(REDIS_QUEUE_KEY, str(job.id))
        except Exception as e:
            logger.warning(f"Could not push job {job.id} to Redis: {e}")

    logger.info(f"Enqueued job {job.id} of type '{job_type}'")
    return job


async def execute_job(job_id: uuid.UUID, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Picks up and executes a single background job with retries and dead-letter handling."""
    job_id_ctx.set(str(job_id))

    async with AsyncSessionLocal() as session:
        job = await session.get(Job, job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found.")

        # Reconcile payload from job model if omitted
        effective_payload = payload if payload is not None else (job.payload or {})

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
            result = await handler(job, effective_payload, session)

            job.status = "completed"
            job.locked_by = None
            job.last_error = None
            await session.commit()
            logger.info(f"Job {job.id} ({job.type}) completed successfully.")
            return result

        except Exception as exc:
            await session.rollback()
            job = await session.get(Job, job_id)
            err_msg = type(exc).__name__ + ": job failed; personal input excluded from diagnostics"
            logger.error(f"Job {job.id} failed on attempt {job.attempts}: {err_msg}")

            if job.attempts >= MAX_JOB_ATTEMPTS:
                job.status = "dead_letter"
                logger.critical(f"Job {job.id} reached MAX_JOB_ATTEMPTS ({MAX_JOB_ATTEMPTS}). Moved to dead_letter.")
                redis_client = await get_redis_client()
                if redis_client:
                    try:
                        await redis_client.rpush(REDIS_DEAD_LETTER_KEY, str(job.id))
                    except Exception:
                        pass
            else:
                if job.type == "submit_application":
                    # External acceptance may be unknown; never automatically click again.
                    job.status = "dead_letter"
                else:
                    job.status = "pending"
                    job.scheduled_for = datetime.now(timezone.utc) + timedelta(seconds=2 ** job.attempts)

            job.last_error = err_msg
            job.locked_by = None
            with recovery_decision("job_failure", ["retry", "dead_letter"]) as decision:
                decision.decide("retry" if job.status == "pending" else "dead_letter",
                    "Internal work may retry; uncertain external submission requires manual reconciliation.")
                decision.finish(job.status)
            await session.commit()
            raise


async def requeue_dead_letter_jobs(job_type: Optional[str] = None) -> int:
    """Requeues dead-letter jobs back to pending status for retry."""
    async with AsyncSessionLocal() as session:
        stmt = select(Job).where(Job.status == "dead_letter")
        if job_type:
            stmt = stmt.where(Job.type == job_type)
        dead_jobs = (await session.execute(stmt)).scalars().all()

        requeued_count = 0
        redis_client = await get_redis_client()
        for j in dead_jobs:
            j.status = "pending"
            j.attempts = 0
            j.last_error = None
            j.locked_by = None
            requeued_count += 1
            if redis_client:
                try:
                    await redis_client.rpush(REDIS_QUEUE_KEY, str(j.id))
                except Exception:
                    pass

        await session.commit()
        logger.info(f"Requeued {requeued_count} dead-letter jobs.")
        return requeued_count


async def fetch_next_pending_job(worker_id: str) -> Optional[Job]:
    """Claim atomically from the database; Redis is a wake-up signal only."""
    client = await get_redis_client()
    if client:
        await client.lpop(REDIS_QUEUE_KEY)
    async with AsyncSessionLocal() as session:
        now = datetime.now(timezone.utc)
        stale = Job.updated_at < now - timedelta(minutes=10)
        await session.execute(update(Job).where(Job.status == "running", stale,
            Job.type != "submit_application").values(status="pending", locked_by=None))
        await session.execute(update(Job).where(Job.status == "running", stale,
            Job.type == "submit_application").values(status="dead_letter", locked_by=None,
            last_error="Worker interrupted; external acceptance must be reconciled manually."))
        await session.commit()
        candidate = (await session.execute(
            select(Job.id).where(Job.status == "pending",
                Job.scheduled_for.is_(None) | (Job.scheduled_for <= now))
            .order_by(Job.created_at).limit(1)
        )).scalar_one_or_none()
        if candidate is None:
            return None
        claimed = await session.execute(update(Job).where(Job.id == candidate, Job.status == "pending")
            .values(status="running", locked_by=worker_id))
        await session.commit()
        if claimed.rowcount != 1:
            return None
        return await session.get(Job, candidate)
