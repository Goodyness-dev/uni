"""Application lifecycle endpoints and approval workflows."""
import uuid
from typing import Annotated, Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.api.deps import get_current_user, get_request_id
from app.db.base import get_db_session
from app.db.models import Application, ApplicationEvent, Draft, Scholarship, User
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

    try:
        await transition_application(
            application=app_record,
            new_status="approved",
            actor="user",
            payload={"approval_action": "user_approved_review"},
            session=db,
        )
    except (IllegalStateTransitionError, KillSwitchActiveError) as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "TRANSITION_ERROR", "message": str(err), "request_id": req_id},
        )

    return await get_application_detail(app_id, user, db, x_request_id)


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

    try:
        await transition_application(
            application=app_record,
            new_status="submitting",
            actor="user",
            payload={"resume_action": "human_completed_blocker"},
            session=db,
        )
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
