"""Submitter Agent: executes idempotent portal submissions, captures screenshots, and hands off on human blockers."""
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.logging import logger
from app.core.security import decrypt_credential
from app.db.models import Application, Draft, Job, Profile, Scholarship, User
from app.integrations.browser_runner import BrowserSubmissionResult, submit_portal
from app.jobs.queue import register_job_handler
from app.jobs.state_machine import IllegalStateTransitionError, KillSwitchActiveError, transition_application


class SubmitterInput(BaseModel):
    application_id: uuid.UUID
    mock_mode: bool = False
    simulated_blocker: Optional[str] = None


class SubmitterOutput(BaseModel):
    application_id: uuid.UUID
    status: str  # submitted, needs_human, already_submitted, failed
    confirmation_ref: Optional[str] = None
    blocker_type: Optional[str] = None
    blocker_message: Optional[str] = None
    screenshot_paths: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


async def run_submitter(
    application_id: uuid.UUID,
    session: AsyncSession,
    mock_mode: bool = False,
    simulated_blocker: Optional[str] = None,
) -> SubmitterOutput:
    """Executes the portal submission workflow for an application.
    
    Hard Rules Enforced:
    1. Idempotency: If already submitted with a confirmation ref, immediately exit with already_submitted.
    2. Autonomy/Review Mode: If application is in ready_for_review, require explicit student approval before submitting.
    3. Blocker Handoff: On CAPTCHA, 2FA, or login wall, capture screenshot and stop cleanly in needs_human state.
    4. Kill Switch: If KILL_SWITCH_ACTIVE is enabled, abort all submissions immediately.
    """
    logger.info(f"Submitter agent invoked for application {application_id}")

    # Fetch application with relations
    application = await session.get(Application, application_id)
    if not application:
        raise ValueError(f"Application {application_id} not found.")

    # 1. Idempotency Guard
    if application.status == "submitted" or application.confirmation_ref is not None:
        logger.info(
            f"Idempotency Guard: Application {application_id} is already submitted (ref: {application.confirmation_ref}). Aborting redundant submission."
        )
        return SubmitterOutput(
            application_id=application.id,
            status="already_submitted",
            confirmation_ref=application.confirmation_ref,
            metadata={"reason": "already_submitted"},
        )

    # 2. Mode and approval checks
    user = await session.get(User, application.user_id)
    scholarship = await session.get(Scholarship, application.scholarship_id)
    if not scholarship:
        raise ValueError(f"Scholarship {application.scholarship_id} not found for application {application_id}.")

    # If application is in review mode and still in ready_for_review, do not submit!
    if application.status == "ready_for_review":
        raise IllegalStateTransitionError(
            f"Application {application_id} is in 'ready_for_review' mode. Submissions require explicit student approval."
        )

    # 3. Transition to 'submitting' if currently in drafting or approved
    if application.status in ("drafting", "approved", "needs_human"):
        application = await transition_application(
            application=application,
            new_status="submitting",
            actor="agent",
            payload={"stage": "portal_submission_started"},
            session=session,
        )

    # 4. Fetch applicant profile and latest draft
    profile = (
        await session.execute(
            select(Profile).where(Profile.user_id == user.id)
        )
    ).scalar_one_or_none()

    draft = (
        await session.execute(
            select(Draft)
            .where(Draft.application_id == application.id)
            .order_by(Draft.version.desc())
        )
    ).scalars().first()

    personal = profile.personal_details if profile and profile.personal_details else {}
    applicant_data = {
        "email": user.email if user else "",
        "first_name": personal.get("first_name", ""),
        "last_name": personal.get("last_name", ""),
        "phone": personal.get("phone", ""),
        "nationality": personal.get("citizenship", "Nigeria"),
        "gpa": str(profile.grades.get("gpa", "")) if profile and profile.grades else "",
    }
    draft_content = draft.content if draft else "Statement of Purpose submitted via ScholarPilot."

    # 5. Execute browser submission via Playwright runner
    portal_url = getattr(scholarship, "application_url", "https://demo.scholarpilot.internal/portal")

    browser_result: BrowserSubmissionResult = await submit_portal(
        portal_url=portal_url,
        applicant_data=applicant_data,
        draft_content=draft_content,
        mock_mode=mock_mode,
        simulated_blocker=simulated_blocker,
    )

    # 6. Evaluate Result and transition state
    if browser_result.is_blocked:
        # Detected CAPTCHA, MFA, login wall, or unexpected fee
        logger.warning(
            f"Submission blocker encountered for application {application_id}: {browser_result.blocker_type}"
        )
        application = await transition_application(
            application=application,
            new_status="needs_human",
            actor="agent",
            payload={
                "blocker_type": browser_result.blocker_type,
                "blocker_message": browser_result.blocker_message,
                "screenshot_paths": browser_result.screenshot_paths,
            },
            session=session,
        )
        return SubmitterOutput(
            application_id=application.id,
            status="needs_human",
            blocker_type=browser_result.blocker_type,
            blocker_message=browser_result.blocker_message,
            screenshot_paths=browser_result.screenshot_paths,
            metadata=browser_result.metadata,
        )

    elif browser_result.success:
        # Successful submission
        logger.info(
            f"Portal submission successful for application {application_id}: {browser_result.confirmation_ref}"
        )
        application.confirmation_ref = browser_result.confirmation_ref
        application.submitted_at = datetime.now(timezone.utc)
        await session.commit()
        await session.refresh(application)

        application = await transition_application(
            application=application,
            new_status="submitted",
            actor="agent",
            payload={
                "confirmation_ref": browser_result.confirmation_ref,
                "screenshot_paths": browser_result.screenshot_paths,
            },
            session=session,
        )
        return SubmitterOutput(
            application_id=application.id,
            status="submitted",
            confirmation_ref=browser_result.confirmation_ref,
            screenshot_paths=browser_result.screenshot_paths,
            metadata=browser_result.metadata,
        )

    else:
        # Submission error/failure
        logger.error(
            f"Submission failed for application {application_id}: {browser_result.blocker_message}"
        )
        application = await transition_application(
            application=application,
            new_status="failed",
            actor="agent",
            payload={
                "error": browser_result.blocker_message or "Unknown submission error",
                "screenshot_paths": browser_result.screenshot_paths,
            },
            session=session,
        )
        return SubmitterOutput(
            application_id=application.id,
            status="failed",
            blocker_message=browser_result.blocker_message,
            screenshot_paths=browser_result.screenshot_paths,
            metadata=browser_result.metadata,
        )


@register_job_handler("submit_application")
async def handle_submit_application_job(job: Job, session: AsyncSession) -> Dict[str, Any]:
    """Queue worker job handler for submit_application tasks."""
    payload = job.payload
    application_id = uuid.UUID(payload["application_id"])
    mock_mode = payload.get("mock_mode", False)
    simulated_blocker = payload.get("simulated_blocker")

    result = await run_submitter(
        application_id=application_id,
        session=session,
        mock_mode=mock_mode,
        simulated_blocker=simulated_blocker,
    )
    return result.model_dump(mode="json")
