"""Owned application batches backed by real Job and application records."""
import uuid
from typing import Annotated, Any, Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user
from app.api.v1.matches import refresh_matches
from app.db.base import get_db_session
from app.db.models import Application, ApplicationEvent, Job, User
from app.jobs.queue import enqueue_job, register_job_handler
from app.jobs.coordinator import run_coordinator_pipeline
from app.jobs.state_machine import transition_application
from app.core.tracing import get_trace_url
from app.core.config import settings
from app.services.discovery import refresh_catalog
from scripts.import_catalog import import_listings
from pathlib import Path

router = APIRouter(prefix="/runs", tags=["Application batches"])


class StartBatch(BaseModel):
    mode: Literal["B"] = "B"
    top_n: int = Field(default=2, ge=1, le=10)
    live_research: bool = False
    tags: list[str] = Field(default_factory=list)


@register_job_handler("application_batch")
async def execute_batch(job: Job, payload: dict[str, Any], session: AsyncSession) -> dict[str, Any]:
    if payload.get("discover") and not payload["application_ids"]:
        await import_listings(Path("backend/data/listings.json"))
        observations = await refresh_catalog(session, limit=6)
        user = await session.get(User, uuid.UUID(payload["user_id"]))
        if user is None or user.status != "active":
            raise ValueError("Applicant is inactive or missing.")
        matches = await refresh_matches(user, session)
        identifiers = await create_batch_applications(matches, user, session)
        payload = {**payload, "application_ids": identifiers, "process_ids": identifiers[:payload.get("top_n", 2)], "discovery": observations}
        job.payload = payload
        await session.commit()
    processed = []
    for application_id in payload.get("process_ids", payload["application_ids"]):
        application = await session.get(Application, uuid.UUID(application_id))
        if application is None or str(application.user_id) != payload["user_id"]:
            continue
        try:
            result = await run_coordinator_pipeline(application.id, session, live_research=payload.get("live_research", False))
        except Exception:
            await session.rollback()
            application = await session.get(Application, uuid.UUID(application_id))
            if application and application.status not in {"submitted", "withdrawn", "expired", "failed"}:
                state = "failed" if application.status in {"researching", "drafting", "submitting", "needs_human"} else "withdrawn"
                await transition_application(application, state, "coordinator",
                    {"reason": "Application processing failed; source content excluded from diagnostics."}, session)
            result = {"application_id": application_id, "status": application.status if application else "failed"}
        processed.append(result)
    return {"applications": processed}


def batch_response(job: Job) -> dict[str, Any]:
    return {"run_id": str(job.id), "mode": "B",
        "status": "completed" if job.status == "completed" else "failed" if job.status in {"failed", "dead_letter"} else "running",
        "started_at": job.created_at.isoformat(), "finished_at": job.updated_at.isoformat() if job.status == "completed" else None,
        "application_ids": job.payload["application_ids"], "metrics": None, "trace_url": get_trace_url(str(job.id))}


async def owned_batch(run_id: uuid.UUID, user: User, db: AsyncSession) -> Job:
    job = await db.get(Job, run_id)
    if not job or job.type != "application_batch" or job.payload.get("user_id") != str(user.id):
        raise HTTPException(status_code=404, detail="Run not found.")
    return job


async def create_batch_applications(matches: list, user: User, db: AsyncSession) -> list[str]:
    applications = []
    for match in sorted(matches, key=lambda entry: entry.fit_score, reverse=True):
        application = Application(user_id=user.id, scholarship_id=uuid.UUID(match.scholarship_id), mode_used=user.mode)
        db.add(application)
        await db.flush()
        db.add(ApplicationEvent(application_id=application.id, actor="user", event_type="application_discovered", payload={"mode": user.mode, "fit_score": match.fit_score, "reasons": match.reasons}))
        applications.append(str(application.id))
    return applications


@router.post("", status_code=202)
async def start_batch(req: StartBatch, user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)]) -> dict[str, str]:
    if req.live_research and not settings.LIVE_RESEARCH:
        raise HTTPException(status_code=400, detail="Live research is disabled by the operator.")
    active = (await db.execute(select(Job).where(Job.type == "application_batch", Job.status.in_(("pending", "running")),
        Job.payload["user_id"].as_string() == str(user.id)))).scalars().first()
    if active:
        raise HTTPException(status_code=409, detail="An application batch is already active.")
    if req.live_research:
        job = await enqueue_job("application_batch", {"user_id": str(user.id), "application_ids": [],
            "process_ids": [], "top_n": req.top_n, "live_research": True, "discover": True}, session=db)
        return {"run_id": str(job.id), "status": "running"}
    matches = await refresh_matches(user, db)
    applications = await create_batch_applications(matches, user, db)
    if not applications:
        raise HTTPException(status_code=400, detail="No eligible scholarships match the profile.")
    job = await enqueue_job("application_batch", {"user_id": str(user.id), "application_ids": applications, "process_ids": applications[:req.top_n], "live_research": req.live_research}, session=db)
    return {"run_id": str(job.id), "status": "running"}


@router.get("/latest")
async def latest_batch(user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db_session)]) -> dict[str, Any]:
    job = (await db.execute(select(Job).where(Job.type == "application_batch",
        Job.payload["user_id"].as_string() == str(user.id)).order_by(Job.created_at.desc()))).scalars().first()
    if job is None:
        raise HTTPException(status_code=404, detail="No runs yet.")
    return batch_response(job)


@router.get("/{run_id}")
async def get_batch(run_id: uuid.UUID, user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)]) -> dict[str, Any]:
    return batch_response(await owned_batch(run_id, user, db))


@router.get("/{run_id}/events")
async def batch_events(run_id: uuid.UUID, user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)], after: int = 0) -> dict[str, Any]:
    job = await owned_batch(run_id, user, db)
    ids = [uuid.UUID(value) for value in job.payload["application_ids"]]
    rows = (await db.execute(select(ApplicationEvent).where(ApplicationEvent.application_id.in_(ids))
        .order_by(ApplicationEvent.created_at, ApplicationEvent.id))).scalars().all()
    events = [{"event_no": index + 1, "at": row.created_at.isoformat(), "run_id": str(run_id),
        "application_id": str(row.application_id), "agent": row.actor, "type": row.event_type,
        "message": row.payload.get("message") or row.payload.get("reason") or row.event_type.replace("_", " "), "data": row.payload} for index, row in enumerate(rows)]
    return {"events": events[max(0, after):], "last_event_no": len(events)}
