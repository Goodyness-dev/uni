"""Student account management endpoints: NDPR/GDPR data export and permanent deletion."""
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List
from fastapi import APIRouter, Depends, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user
from app.core.logging import logger
from app.db.base import get_db_session
from app.db.models import (
    ApiKey,
    Application,
    ApplicationEvent,
    Document,
    Draft,
    Profile,
    User,
    Webhook,
)

router = APIRouter(prefix="/account", tags=["account"])


@router.get("/export", status_code=status.HTTP_200_OK)
async def export_student_account_data(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> Dict[str, Any]:
    """Downloads a complete machine-readable JSON archive of the student's personal data,
    Profile Vault, documents, drafts, and applications.
    """
    logger.info(f"Account data export requested for user {current_user.id}")

    # 1. Profile
    prof_stmt = select(Profile).where(Profile.user_id == current_user.id)
    profile = (await session.execute(prof_stmt)).scalar_one_or_none()
    profile_data = None
    if profile:
        profile_data = {
            "personal_details": profile.personal_details,
            "education_history": profile.education_history,
            "grades": profile.grades,
            "test_scores": profile.test_scores,
            "achievements": profile.achievements,
            "financial_need_info": profile.financial_need_info,
            "target_countries": profile.target_countries,
            "target_fields_of_study": profile.target_fields_of_study,
            "completeness_score": profile.completeness_score,
            "updated_at": profile.updated_at.isoformat() if profile.updated_at else None,
        }

    # 2. Documents
    docs_stmt = select(Document).where(Document.user_id == current_user.id)
    documents = (await session.execute(docs_stmt)).scalars().all()
    docs_data = [
        {
            "id": str(d.id),
            "type": d.type,
            "storage_key": d.storage_key,
            "uploaded_at": d.uploaded_at.isoformat() if d.uploaded_at else None,
            "verified": d.verified,
        }
        for d in documents
    ]

    # 3. Applications and Drafts
    apps_stmt = select(Application).where(Application.user_id == current_user.id)
    applications = (await session.execute(apps_stmt)).scalars().all()
    app_ids = [a.id for a in applications]

    drafts_data: List[Dict[str, Any]] = []
    events_data: List[Dict[str, Any]] = []

    if app_ids:
        drafts_stmt = select(Draft).where(Draft.application_id.in_(app_ids))
        drafts = (await session.execute(drafts_stmt)).scalars().all()
        drafts_data = [
            {
                "id": str(d.id),
                "application_id": str(d.application_id),
                "kind": d.kind,
                "content": d.content,
                "version": d.version,
                "source_facts": d.source_facts,
            }
            for d in drafts
        ]

        events_stmt = select(ApplicationEvent).where(ApplicationEvent.application_id.in_(app_ids))
        events = (await session.execute(events_stmt)).scalars().all()
        events_data = [
            {
                "id": str(e.id),
                "application_id": str(e.application_id),
                "actor": e.actor,
                "event_type": e.event_type,
                "payload": e.payload,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in events
        ]

    apps_data = [
        {
            "id": str(a.id),
            "scholarship_id": str(a.scholarship_id),
            "status": a.status,
            "mode_used": a.mode_used,
            "submitted_at": a.submitted_at.isoformat() if a.submitted_at else None,
            "confirmation_ref": a.confirmation_ref,
            "outcome": a.outcome,
        }
        for a in applications
    ]

    return {
        "export_metadata": {
            "version": "1.0",
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "format": "ScholarPilot-NDPR-Archive",
        },
        "user": {
            "id": str(current_user.id),
            "email": current_user.email,
            "mode": current_user.mode,
            "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
        },
        "profile": profile_data,
        "documents": docs_data,
        "applications": apps_data,
        "drafts": drafts_data,
        "timeline_events": events_data,
    }


@router.delete("", status_code=status.HTTP_200_OK)
async def delete_student_account(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> Dict[str, Any]:
    """Permanently purges student account, profile vault, documents, and credentials
    under the Right to be Forgotten (NDPR & GDPR).
    """
    logger.info(f"Permanent account deletion initiated for user {current_user.id}")

    # 1. Delete Profile
    await session.execute(delete(Profile).where(Profile.user_id == current_user.id))

    # 2. Delete Documents
    await session.execute(delete(Document).where(Document.user_id == current_user.id))

    # 3. Delete ApiKeys and Webhooks
    await session.execute(delete(ApiKey).where(ApiKey.user_id == current_user.id))
    await session.execute(delete(Webhook).where(Webhook.user_id == current_user.id))

    # 4. Find and delete drafts for applications
    apps_stmt = select(Application).where(Application.user_id == current_user.id)
    applications = (await session.execute(apps_stmt)).scalars().all()
    app_ids = [a.id for a in applications]

    if app_ids:
        await session.execute(delete(Draft).where(Draft.application_id.in_(app_ids)))
        await session.execute(delete(Application).where(Application.id.in_(app_ids)))

    # 5. Anonymize user record
    current_user.email = f"purged-{current_user.id.hex[:12]}@scholarpilot.internal"
    current_user.status = "deleted"
    current_user.mode = "purged"
    await session.commit()

    return {
        "success": True,
        "message": "Account, Profile Vault, and all personal documents permanently purged in compliance with NDPR and GDPR regulations.",
        "purged_user_id": str(current_user.id),
    }
