"""Application lifecycle endpoints and approval workflows."""
import uuid
from datetime import datetime, timezone
import httpx
from app.integrations.demo_portal import read_confirmation
from typing import Annotated, Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from fastapi.responses import FileResponse
from app.agents.packager import package_path
from app.core.tracing import get_trace_url
from app.core.config import settings
from app.core.runtime import is_demo_portal
from app.api.deps import get_current_user, get_request_id
from app.db.base import get_db_session
from app.db.models import Application, ApplicationEvent, Draft, Scholarship, User
from app.jobs.queue import enqueue_job, get_redis_client
from app.jobs.state_machine import (
    IllegalStateTransitionError,
    KillSwitchActiveError,
    transition_application,
)

router = APIRouter(prefix="/applications", tags=["Applications"])


class StartApplicationRequest(BaseModel):
    scholarship_id: uuid.UUID
    mode: Optional[str] = None  # autopilot, review (defaults to user.mode)


class ApplicationEventItem(BaseModel):
    id: str
    actor: str
    event_type: str
    payload: Dict[str, Any]
    created_at: str


class DraftItem(BaseModel):
    id: str
    kind: str
    version: int
    content: str
    source_facts: List[str]
    created_at: str


class ApplicationDetailResponse(BaseModel):
    id: str
    user_id: str
    scholarship_id: str
    scholarship_title: Optional[str] = None
    status: str
    mode_used: str
    submitted_at: Optional[str] = None
    confirmation_ref: Optional[str] = None
    outcome: Optional[str] = None
    created_at: str
    events: List[ApplicationEventItem] = Field(default_factory=list)
    drafts: List[DraftItem] = Field(default_factory=list)
    listing: Optional[Dict[str, Any]] = None
    verification: Optional[Dict[str, Any]] = None
    package: Optional[Dict[str, str]] = None
    handoff: Optional[Dict[str, str]] = None
    trace_url: Optional[str] = None


class ApplicationListItem(BaseModel):
    id: str
    user_id: str
    scholarship_id: str
    scholarship_title: str
    status: str
    mode_used: str
    submitted_at: Optional[str] = None
    created_at: str


@router.post("", response_model=ApplicationDetailResponse, status_code=status.HTTP_201_CREATED)
async def start_application(
    req: StartApplicationRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    x_request_id: Optional[str] = Header(None),
) -> ApplicationDetailResponse:
    """Starts a new scholarship application lifecycle in 'discovered' state."""
    req_id = get_request_id(x_request_id)

    schol = await db.get(Scholarship, req.scholarship_id)
    if not schol or schol.status != "active":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "SCHOLARSHIP_NOT_FOUND", "message": "Scholarship not found.", "request_id": req_id},
        )

    mode = req.mode or user.mode
    if mode not in {"autopilot", "review"}:
        raise HTTPException(status_code=400, detail="Unknown application mode.")
    app_record = Application(
        user_id=user.id,
        scholarship_id=schol.id,
        status="discovered",
        mode_used=mode,
    )
    db.add(app_record)
    await db.commit()
    await db.refresh(app_record)

    # Initial event log
    init_event = ApplicationEvent(
        application_id=app_record.id,
        actor="user",
        event_type="application_discovered",
        payload={"initial_mode": mode, "scholarship_title": schol.title},
    )
    db.add(init_event)
    await db.commit()
    await db.refresh(init_event)

    # Enqueue coordinator pipeline to run matching, research, and drafting asynchronously
    await enqueue_job(
        "coordinator_pipeline",
        {
            "application_id": str(app_record.id),
            "user_id": str(user.id),
            "scholarship_id": str(schol.id),
        },
        session=db,
    )

    return ApplicationDetailResponse(
        id=str(app_record.id),
        user_id=str(app_record.user_id),
        scholarship_id=str(app_record.scholarship_id),
        scholarship_title=schol.title,
        status=app_record.status,
        mode_used=app_record.mode_used,
        created_at=app_record.created_at.isoformat(),
        events=[
            ApplicationEventItem(
                id=str(init_event.id),
                actor=init_event.actor,
                event_type=init_event.event_type,
                payload=init_event.payload,
                created_at=init_event.created_at.isoformat(),
            )
        ],
        drafts=[],
    )


@router.get("", response_model=List[ApplicationListItem])
async def list_applications(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    status_filter: Optional[str] = Query(None, alias="status"),
) -> List[ApplicationListItem]:
    """Lists applications belonging to the authenticated user."""
    stmt = (
        select(Application, Scholarship)
        .join(Scholarship, Application.scholarship_id == Scholarship.id)
        .where(Application.user_id == user.id)
    )
    if status_filter:
        stmt = stmt.where(Application.status == status_filter)

    stmt = stmt.order_by(Application.created_at.desc())
    rows = (await db.execute(stmt)).all()

    return [
        ApplicationListItem(
            id=str(app_row.id),
            user_id=str(app_row.user_id),
            scholarship_id=str(schol.id),
            scholarship_title=schol.title,
            status=app_row.status,
            mode_used=app_row.mode_used,
            submitted_at=app_row.submitted_at.isoformat() if app_row.submitted_at else None,
            created_at=app_row.created_at.isoformat(),
        )
        for app_row, schol in rows
    ]


@router.get("/{app_id}", response_model=ApplicationDetailResponse)
async def get_application_detail(
    app_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    x_request_id: Optional[str] = Header(None),
) -> ApplicationDetailResponse:
    """Retrieves full application details with drafts and audit timeline."""
    req_id = get_request_id(x_request_id)

    stmt = (
        select(Application)
        .options(
            selectinload(Application.events),
            selectinload(Application.drafts),
            selectinload(Application.scholarship),
        )
        .where(Application.id == app_id, Application.user_id == user.id)
    )
    app_record = (await db.execute(stmt)).scalar_one_or_none()

    if not app_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "APPLICATION_NOT_FOUND", "message": "Application not found.", "request_id": req_id},
        )

    verification_event = next((event for event in reversed(sorted(app_record.events, key=lambda entry: entry.created_at))
        if event.event_type == "verification_report"), None)
    handoff_event = next((event for event in reversed(sorted(app_record.events, key=lambda entry: entry.created_at))
        if event.payload.get("portal_url")), None)
    files = {"cv_pdf_url": f"/v1/applications/{app_id}/files/cv", "essay_url": f"/v1/applications/{app_id}/files/essay",
        "checklist_url": f"/v1/applications/{app_id}/files/checklist"}
    complete_package = all(package_path(user.id, app_id, kind).is_file() for kind in ("cv", "essay", "checklist"))

    return ApplicationDetailResponse(
        id=str(app_record.id),
        user_id=str(app_record.user_id),
        scholarship_id=str(app_record.scholarship_id),
        scholarship_title=app_record.scholarship.title if app_record.scholarship else None,
        status=app_record.status,
        mode_used=app_record.mode_used,
        submitted_at=app_record.submitted_at.isoformat() if app_record.submitted_at else None,
        confirmation_ref=app_record.confirmation_ref,
        outcome=app_record.outcome,
        created_at=app_record.created_at.isoformat(),
        listing={"id": str(app_record.scholarship.id), "name": app_record.scholarship.title,
            "level": app_record.scholarship.level, "provider": app_record.scholarship.provider, "country": app_record.scholarship.country,
            "deadline": app_record.scholarship.deadline.isoformat() if app_record.scholarship.deadline else "",
            "source_url": app_record.scholarship.application_url, **app_record.scholarship.eligibility_rules},
        verification=verification_event.payload.get("report") if verification_event else None,
        package=files if complete_package else None,
        trace_url=(("https://eu.app.neatlogs.com" if "eu.ingest." in (settings.NEATLOGS_ENDPOINT or "") else "https://app.neatlogs.com") + "/traces/" + next(event.payload["trace_id"] for event in reversed(sorted(app_record.events, key=lambda item: item.created_at)) if event.event_type == "neatlogs_trace")
            if any(event.event_type == "neatlogs_trace" for event in app_record.events) else get_trace_url(str(app_id))),
        handoff={"reason": handoff_event.payload.get("blocker_type", "review"), "portal_url": handoff_event.payload["portal_url"],
            "instructions": handoff_event.payload.get("instructions", "Open the demo portal, complete the security step yourself, submit, then select Resume.")}
            if handoff_event and app_record.status == "needs_human" else None,
        events=[
            ApplicationEventItem(
                id=str(e.id),
                actor=e.actor,
                event_type=e.event_type,
                payload=e.payload,
                created_at=e.created_at.isoformat(),
            )
            for e in app_record.events
        ],
        drafts=[
            DraftItem(
                id=str(d.id),
                kind=d.kind,
                version=d.version,
                content=d.content,
                source_facts=d.source_facts,
                created_at=d.created_at.isoformat(),
            )
            for d in app_record.drafts
        ],
    )


@router.post("/{app_id}/approve", response_model=ApplicationDetailResponse)
async def approve_application(
    app_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    x_request_id: Optional[str] = Header(None),
) -> ApplicationDetailResponse:
    """Approves an application in Review mode for submission."""
    req_id = get_request_id(x_request_id)
    app_record = await db.get(Application, app_id)

    if not app_record or app_record.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "APPLICATION_NOT_FOUND", "message": "Application not found.", "request_id": req_id},
        )

    draft = (await db.execute(select(Draft).where(Draft.application_id == app_id, Draft.kind.in_(("essay", "statement"))).order_by(Draft.version.desc()))).scalars().first()
    if draft is None or not draft.content.strip():
        raise HTTPException(status_code=400, detail="Review requires a nonempty source-supported draft.")
    try:
        await transition_application(
            application=app_record,
            new_status="approved",
            actor="user",
            payload={"approval_action": "user_approved_review"},
            session=db,
        )
        scholarship = await db.get(Scholarship, app_record.scholarship_id)
        if is_demo_portal(scholarship.application_url) and scholarship.eligibility_rules.get("ai_policy", "unknown") in {"allowed", "disclose"}:
            await enqueue_job("submit_application", {"application_id": str(app_id)}, session=db)
    except (IllegalStateTransitionError, KillSwitchActiveError) as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "TRANSITION_ERROR", "message": str(err), "request_id": req_id},
        )

    return await get_application_detail(app_id, user, db, x_request_id)


@router.get("/{app_id}/files/{kind}")
async def download_package(app_id: uuid.UUID, kind: str, user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)]) -> FileResponse:
    application = await db.get(Application, app_id)
    if application is None or application.user_id != user.id:
        raise HTTPException(status_code=404, detail="Application not found.")
    try:
        path = package_path(user.id, app_id, kind)
    except ValueError:
        raise HTTPException(status_code=404, detail="Package file not found.")
    if not path.is_file() or path.is_symlink():
        raise HTTPException(status_code=404, detail="Package file not found.")
    return FileResponse(path, media_type="application/pdf" if kind == "cv" else "text/plain", filename=path.name)


@router.post("/{app_id}/resume", response_model=ApplicationDetailResponse)
async def resume_application(
    app_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    x_request_id: Optional[str] = Header(None),
) -> ApplicationDetailResponse:
    """Resumes an application from 'needs_human' back to 'submitting'."""
    req_id = get_request_id(x_request_id)
    app_record = await db.get(Application, app_id)

    if not app_record or app_record.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "APPLICATION_NOT_FOUND", "message": "Application not found.", "request_id": req_id},
        )

    if app_record.status != "needs_human":
        raise HTTPException(status_code=409, detail="Application is not awaiting human completion.")
    events = (await db.execute(select(ApplicationEvent).where(ApplicationEvent.application_id == app_id).order_by(ApplicationEvent.created_at.desc()))).scalars().all()
    portal_url = next((event.payload["portal_url"] for event in events if event.payload.get("portal_url")), None)
    if not portal_url or not is_demo_portal(portal_url):
        raise HTTPException(status_code=409, detail="No owned demo draft is available for reconciliation.")
    try:
        confirmation = await read_confirmation(portal_url)
    except (httpx.HTTPError, ValueError, KeyError):
        raise HTTPException(status_code=503, detail="Portal confirmation could not be checked.")
    if not confirmation:
        raise HTTPException(status_code=409, detail="Complete the demo submission yourself before selecting Resume. No submission was retried.")
    try:
        await transition_application(
            application=app_record,
            new_status="submitting",
            actor="user",
            payload={"resume_action": "human_completed_blocker"},
            session=db,
        )
        app_record.confirmation_ref = confirmation
        app_record.submitted_at = datetime.now(timezone.utc)
        await transition_application(app_record, "submitted", "user", {"confirmation_ref": confirmation, "reconciled_after_handoff": True}, db)
    except (IllegalStateTransitionError, KillSwitchActiveError) as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "TRANSITION_ERROR", "message": str(err), "request_id": req_id},
        )

    return await get_application_detail(app_id, user, db, x_request_id)


@router.post("/{app_id}/withdraw", response_model=ApplicationDetailResponse)
async def withdraw_application(
    app_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    x_request_id: Optional[str] = Header(None),
) -> ApplicationDetailResponse:
    """Cancels and withdraws an in-flight application."""
    req_id = get_request_id(x_request_id)
    app_record = await db.get(Application, app_id)

    if not app_record or app_record.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "APPLICATION_NOT_FOUND", "message": "Application not found.", "request_id": req_id},
        )

    broker = await get_redis_client()
    if broker is None:
        raise HTTPException(status_code=503, detail="Cancellation requires the shared worker broker.")
    await broker.set("scholarpilot:application_cancelled:" + str(app_id), "1")
    try:
        await transition_application(
            application=app_record,
            new_status="withdrawn",
            actor="user",
            payload={"user_requested_withdrawal": True},
            session=db,
        )
    except IllegalStateTransitionError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "TRANSITION_ERROR", "message": str(err), "request_id": req_id},
        )

    return await get_application_detail(app_id, user, db, x_request_id)


@router.post("/{app_id}/continue", status_code=202)
async def continue_application(app_id: uuid.UUID, user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)]) -> dict[str, str]:
    application = await db.get(Application, app_id)
    if not application or application.user_id != user.id:
        raise HTTPException(status_code=404, detail="Application not found.")
    events = (await db.execute(select(ApplicationEvent).where(ApplicationEvent.application_id == app_id)
        .order_by(ApplicationEvent.created_at.desc()))).scalars().all()
    request = next((e for e in events if e.payload.get("blocker_type") == "missing_evidence"), None)
    if application.status != "needs_human" or not request:
        raise HTTPException(status_code=409, detail="This application is not waiting for source evidence.")
    if sum(e.event_type == "evidence_resume" for e in events) >= 2:
        raise HTTPException(status_code=409, detail="Evidence continuation limit reached.")
    await transition_application(application, "researching", "user", {"message": "Applicant supplied source evidence; continuing agent."}, db)
    db.add(ApplicationEvent(application_id=app_id, actor="user", event_type="evidence_resume", payload={}))
    await db.commit()
    job = await enqueue_job("coordinator_pipeline", {"application_id": str(app_id)}, session=db)
    return {"application_id": str(app_id), "job_id": str(job.id), "status": application.status}
