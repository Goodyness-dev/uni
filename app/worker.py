"""Long-running background worker process for ScholarPilot task queue."""
import asyncio
import signal
import sys
import uuid
import time
from typing import Optional
from app.core.config import settings
from app.core.logging import logger, setup_logging
from app.db.base import AsyncSessionLocal
from app.jobs.queue import (
    execute_job,
    fetch_next_pending_job,
    get_redis_client,
    requeue_dead_letter_jobs,
)
# Ensure all job handlers are imported and registered
import app.agents.submitter
import app.agents.matcher
import app.agents.researcher
import app.agents.edge_finder
import app.agents.drafter
import app.jobs.coordinator
from app.services.scheduler import schedule_daily_cycles
from app.core.tracing import init_tracing, shutdown_tracing


class Worker:
    """Asynchronous background worker polling and processing queued jobs."""

    def __init__(self, worker_id: Optional[str] = None):
        self.worker_id = worker_id or f"worker_{uuid.uuid4().hex[:8]}"
        self.running = False
        self._stop_event = asyncio.Event()

    async def start(self):
        """Starts the worker processing loop."""
        setup_logging(settings.LOG_LEVEL)
        init_tracing(tags=["worker"])
        logger.info(f"ScholarPilot background worker {self.worker_id} starting up...")
        self.running = True

        redis_client = await get_redis_client()
        if redis_client:
            logger.info("Worker attached to Redis task broker.")
        else:
            logger.info("Redis not detected; worker running against PostgreSQL/database queue.")

        # Requeue any dead-letter jobs on startup if desired or check health
        poll_interval = 1.0
        next_schedule_tick = 0.0

        try:
            while not self._stop_event.is_set():
                if time.monotonic() >= next_schedule_tick:
                    async with AsyncSessionLocal() as session:
                        await schedule_daily_cycles(session)
                    next_schedule_tick = time.monotonic() + 60.0
                job = await fetch_next_pending_job(self.worker_id)
                if job:
                    logger.info(f"Worker {self.worker_id} picked up job {job.id} ({job.type})")
                    try:
                        await execute_job(job.id, job.payload)
                    except Exception as err:
                        logger.error("Worker job failed (%s); input excluded.", type(err).__name__)
                else:
                    try:
                        await asyncio.wait_for(self._stop_event.wait(), timeout=poll_interval)
                    except asyncio.TimeoutError:
                        pass
        except asyncio.CancelledError:
            logger.info(f"Worker {self.worker_id} received cancel request.")
        finally:
            self.running = False
            shutdown_tracing()
            logger.info(f"Worker {self.worker_id} stopped cleanly.")

    def stop(self):
        """Signals the worker to stop processing new tasks."""
        logger.info(f"Stopping worker {self.worker_id}...")
        self._stop_event.set()


async def main():
    """Main entrypoint for worker service."""
    worker = Worker()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, worker.stop)
        except NotImplementedError:
            # Signal handlers not implemented on Windows event loop for some signals
            pass

    await worker.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        sys.exit(0)
