from typing import Any
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app import db
from app.coordinator import resume_run, start_run_thread
from app.models import Event, RunMetrics

router = APIRouter(prefix="/api/runs", tags=["runs"])


class CreateRunRequest(BaseModel):
    mode: str = "B"
    top_n: int = 2
    live_research: bool = False
    tags: list[str] = Field(default_factory=list)


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def create_run_endpoint(req: CreateRunRequest) -> dict[str, str]:
    # 1. Facts check
    facts = db.get_facts()
    if not facts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No applicant facts exist. Please run intake or load demo profile first.",
        )

    # 2. Concurrency check: 409 if a run is already running
    latest = db.latest_run()
    if latest and latest.get("status") == "running":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Run {latest['run_id']} is already running.",
        )

    # 3. Create run row
    run_id = db.create_run(req.mode, req.top_n, req.live_research)

    # 4. Start execution thread
    start_run_thread(run_id)

    return {"run_id": run_id, "status": "running"}


@router.get("/latest")
def get_latest_run_endpoint() -> dict[str, Any]:
    run = db.latest_run()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No runs found")
    return run


@router.get("/{run_id}")
def get_run_endpoint(run_id: str) -> dict[str, Any]:
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Run {run_id} not found")
    return run


@router.get("/{run_id}/events")
def get_run_events_endpoint(run_id: str, after: int = Query(0, ge=0)) -> dict[str, Any]:
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Run {run_id} not found")

    events = db.list_events(run_id, after=after)
    last_event_no = events[-1]["event_no"] if events else after
    return {
        "events": events,
        "last_event_no": last_event_no,
    }


@router.post("/{run_id}/resume", status_code=status.HTTP_202_ACCEPTED)
def resume_run_endpoint(run_id: str) -> dict[str, str]:
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Run {run_id} not found")

    if run["status"] not in ("interrupted", "failed"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Run {run_id} has status '{run['status']}'. Only interrupted or failed runs can be resumed.",
        )

    resume_run(run_id)
    return {"run_id": run_id, "status": "running"}
