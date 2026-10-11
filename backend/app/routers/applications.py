import os
from pathlib import Path
from typing import Any
from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import BaseModel

from app import db
from app.agents import scout

router = APIRouter(prefix="/api/applications", tags=["applications"])


@router.get("")
def list_applications_endpoint(run_id: str | None = Query(None)) -> dict[str, list[dict[str, Any]]]:
    target_run_id = run_id
    if not target_run_id:
        latest = db.latest_run()
        if latest:
            target_run_id = latest["run_id"]

    if not target_run_id:
        return {"applications": []}

    apps = db.list_applications(target_run_id)
    summaries = []
    for app in apps:
        listing = scout.get_listing(app["listing_id"])
        summaries.append({
            "id": app["id"],
            "listing_id": app["listing_id"],
            "name": listing.name if listing else app["listing_id"],
            "is_mock": listing.is_mock if listing else False,
            "status": app["status"],
            "channel": app["channel"],
            "fit_score": app["fit_score"],
            "deadline": listing.deadline if listing else "",
            "updated_at": app.get("updated_at") or "",
        })
    return {"applications": summaries}


@router.get("/{app_id}")
def get_application_endpoint(app_id: str) -> dict[str, Any]:
    app = db.get_application(app_id)
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Application {app_id} not found")

    listing = scout.get_listing(app["listing_id"])
    run = db.get_run(app["run_id"])

    # Package URLs mapping if package exists
    package_data = app.get("package")
    package_urls = None
    if package_data:
        package_urls = {
            "cv_pdf_url": f"/api/applications/{app_id}/files/cv",
            "essay_url": f"/api/applications/{app_id}/files/essay",
            "checklist_url": f"/api/applications/{app_id}/files/checklist",
        }

    # Submission default
    submission = app.get("submission") or {
        "confirmed": False,
        "confirmation_code": None,
        "channel": app.get("channel", ""),
        "at": None,
    }

    # Notifications & Timeline
    notifications = db.list_notifications(app_id)
    timeline = db.list_application_events(app_id)

    return {
        "id": app["id"],
        "run_id": app["run_id"],
        "listing": listing.model_dump() if listing else None,
        "status": app["status"],
        "fit_score": app["fit_score"],
        "fit_reason": app["fit_reason"],
        "failure_reason": app["failure_reason"],
        "dossier": app.get("dossier"),
        "edges": app.get("edges") or [],
        "tailored": app.get("tailored"),
        "verification": app.get("verification"),
        "package": package_urls,
        "handoff": app.get("handoff"),
        "submission": submission,
        "notifications": notifications,
        "timeline": timeline,
        "trace_url": run.get("trace_url") if run else None,
        "metrics": app.get("metrics"),
    }


@router.get("/{app_id}/files/{kind}")
def get_application_file_endpoint(app_id: str, kind: str) -> Response:
    if kind not in ("cv", "essay", "checklist"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown file kind {kind}")

    app = db.get_application(app_id)
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Application {app_id} not found")

    pkg = app.get("package") or {}
    file_map = {
        "cv": pkg.get("cv_pdf", f"backend/data/packages/{app_id}/cv.pdf"),
        "essay": pkg.get("essay_txt", f"backend/data/packages/{app_id}/essay.txt"),
        "checklist": pkg.get("checklist_txt", f"backend/data/packages/{app_id}/checklist.txt"),
    }

    raw_path = file_map[kind]
    candidates = [
        Path(raw_path),
        Path("backend/data/packages") / raw_path,
        Path("data/packages") / raw_path,
        Path(__file__).resolve().parent.parent.parent / "data" / "packages" / raw_path,
        Path("backend/data/packages") / app_id / (f"{kind}.pdf" if kind == "cv" else f"{kind}.txt"),
        Path("data/packages") / app_id / (f"{kind}.pdf" if kind == "cv" else f"{kind}.txt"),
    ]
    file_path = None
    for cand in candidates:
        if cand.is_file():
            file_path = cand
            break

    if not file_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"File {kind} not generated yet")

    content = file_path.read_bytes()
    media_type = "application/pdf" if kind == "cv" else "text/plain; charset=utf-8"
    return Response(content=content, media_type=media_type)


@router.post("/{app_id}/handoff/done", status_code=status.HTTP_202_ACCEPTED)
def handoff_done_endpoint(app_id: str) -> dict[str, str]:
    app = db.get_application(app_id)
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Application {app_id} not found")

    if app["status"] != "awaiting_user":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Application {app_id} has status '{app['status']}', not 'awaiting_user'",
        )

    db.set_status(app_id, "submitting", "User confirmed CAPTCHA completion", agent="coordinator")
    return {"status": "submitting"}
