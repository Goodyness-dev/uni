"""Application lifecycle state machine and append-only event logger."""
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Set
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.logging import logger
from app.db.models import Application, ApplicationEvent
from app.services.notifications import queue_notifications


class IllegalStateTransitionError(Exception):
    """Raised when an illegal lifecycle state transition is attempted."""
    pass


class KillSwitchActiveError(Exception):
    """Raised when an action is blocked by the global kill switch."""
    pass


# 12 Valid Application States
VALID_APPLICATION_STATES: Set[str] = {
    "discovered",
    "matched",
    "researching",
    "drafting",
    "ready_for_review",
    "approved",
    "submitting",
    "needs_human",
    "submitted",
    "failed",
    "expired",
    "withdrawn",
}

# Allowed Directed State Transitions
ALLOWED_TRANSITIONS: Dict[str, Set[str]] = {
    "discovered": {"matched", "withdrawn", "expired"},
    "matched": {"researching", "withdrawn", "expired"},
    "researching": {"drafting", "needs_human", "failed", "withdrawn", "expired"},
    "drafting": {"ready_for_review", "needs_human", "submitting", "failed", "withdrawn", "expired"},
    "ready_for_review": {"approved", "withdrawn", "expired"},
    "approved": {"submitting", "withdrawn", "expired"},
    "submitting": {"submitted", "needs_human", "failed", "withdrawn"},
    "needs_human": {"researching", "drafting", "submitting", "failed", "withdrawn", "expired"},
    "submitted": set(),  # Terminal
    "failed": {"drafting", "submitting", "withdrawn", "expired"},  # Retry states
    "expired": set(),    # Terminal
    "withdrawn": set(),  # Terminal
}


async def transition_application(
    application: Application,
    new_status: str,
    actor: str,  # agent, user, system
    payload: Dict[str, Any],
    session: AsyncSession,
) -> Application:
    """Enforces valid state machine transition and records append-only event."""
    if new_status not in VALID_APPLICATION_STATES:
        raise IllegalStateTransitionError(f"Unknown target application state: '{new_status}'")

    current_status = application.status

    # Validate transition
    allowed_next = ALLOWED_TRANSITIONS.get(current_status, set())
    if new_status not in allowed_next:
        raise IllegalStateTransitionError(
            f"Illegal state transition: cannot transition application from '{current_status}' to '{new_status}'."
        )

    # Review mode guard: in review mode, drafting must stop at ready_for_review
    if current_status == "drafting" and new_status == "submitting" and application.mode_used == "review":
        raise IllegalStateTransitionError(
            "Review mode violation: Application in Review mode must transition to 'ready_for_review', not 'submitting'."
        )

    # Emergency kill switch enforcement
    if new_status in {"submitting", "submitted"} and settings.KILL_SWITCH_ACTIVE:
        raise KillSwitchActiveError("Global kill switch is active. Submissions are halted.")

    # Apply state update
    old_status = application.status
    application.status = new_status

    if new_status == "submitted" and not application.submitted_at:
        application.submitted_at = datetime.now(timezone.utc)

    # Append-only audit logging in application_events
    event = ApplicationEvent(
        application_id=application.id,
        actor=actor,
        event_type=f"status_changed_{new_status}",
        payload={
            "from_status": old_status,
            "to_status": new_status,
            "mode": application.mode_used,
            **payload,
        },
    )
    session.add(event)
    await session.commit()
    await session.refresh(application)

    if new_status in {"needs_human", "ready_for_review", "submitted", "failed"}:
        await queue_notifications(application, session)
    logger.info(f"Application {application.id} transitioned from '{old_status}' to '{new_status}' by {actor}")
    return application
