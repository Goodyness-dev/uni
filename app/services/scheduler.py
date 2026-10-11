"""Production scheduler: daily discovery/matching loop per user timezone and proactive deadline alerts."""
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.agents.matcher import run_matcher
from app.core.logging import logger
from app.db.models import Application, Match, Profile, Scholarship, User
from app.integrations.telegram import format_deadline_alert, send_telegram_message
from app.integrations.webhooks import dispatch_user_webhooks


async def scan_upcoming_deadlines(
    session: AsyncSession,
    reference_time: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """Scans catalog and applications for scholarships approaching cutoff (7d, 3d, 1d).
    
    Returns structured list of deadline alerts for proactive notification.
    """
    ref = reference_time or datetime.now(timezone.utc)
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=timezone.utc)

    # Fetch all active scholarships with a valid deadline
    stmt = select(Scholarship).where(Scholarship.status == "active", Scholarship.deadline.isnot(None))
    result = await session.execute(stmt)
    scholarships = result.scalars().all()

    alerts: List[Dict[str, Any]] = []

    for s in scholarships:
        d = s.deadline
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)

        delta = d - ref
        total_seconds = delta.total_seconds()
        days_remaining = total_seconds / 86400.0

        bucket: Optional[str] = None
        if 0.0 <= days_remaining <= 1.0:
            bucket = "1d"
        elif 1.0 < days_remaining <= 3.0:
            bucket = "3d"
        elif 3.0 < days_remaining <= 7.0:
            bucket = "7d"

        if bucket is not None:
            # Find users who have active applications or matches for this scholarship
            app_stmt = select(Application).where(
                Application.scholarship_id == s.id,
                Application.status.not_in(["submitted", "withdrawn", "expired"]),
            )
            apps = (await session.execute(app_stmt)).scalars().all()
            user_ids = list({a.user_id for a in apps})

            # If no applications yet, check ranked matches
            if not user_ids:
                match_stmt = select(Match).where(Match.scholarship_id == s.id)
                matches = (await session.execute(match_stmt)).scalars().all()
                user_ids = list({m.user_id for m in matches})

            alerts.append({
                "scholarship_id": s.id,
                "title": s.title,
                "deadline": d.strftime("%Y-%m-%d"),
                "days_remaining": max(1, round(days_remaining)),
                "bucket": bucket,
                "user_ids": user_ids,
            })

    return alerts


async def run_daily_discovery_and_matching(
    session: AsyncSession,
    target_timezone: Optional[str] = None,
) -> Dict[str, Any]:
    """Runs daily scholarship discovery and profile matching for active users."""
    stmt = select(User).where(User.status == "active")
    users = (await session.execute(stmt)).scalars().all()

    total_matches_generated = 0
    users_processed = 0

    for user in users:
        # Check if user has a profile
        prof_stmt = select(Profile).where(Profile.user_id == user.id)
        profile = (await session.execute(prof_stmt)).scalar_one_or_none()
        if not profile:
            continue

        try:
            # Run deterministic matching
            matcher_output = await run_matcher(user.id, session)
            matches = matcher_output.matches
            total_matches_generated += len(matches)
            users_processed += 1

            # Dispatch webhook notification if matches found
            if matches:
                await dispatch_user_webhooks(
                    user_id=user.id,
                    event_type="matches.refreshed",
                    payload={"new_matches_count": len(matches)},
                    session=session,
                )
        except Exception as e:
            logger.error(f"Error running daily matching for user {user.id}: {e}")

    return {
        "users_processed": users_processed,
        "matches_generated": total_matches_generated,
    }


async def run_daily_scheduler_cycle(
    session: AsyncSession,
    reference_time: Optional[datetime] = None,
    target_timezone: Optional[str] = None,
) -> Dict[str, Any]:
    """Executes full autonomous daily cycle:
    1. Discovery and profile matching
    2. Proactive deadline monitoring (7d, 3d, 1d)
    3. Signed webhook and Telegram alerts
    """
    logger.info("Starting autonomous daily scheduler cycle")

    # 1. Matching
    matching_summary = await run_daily_discovery_and_matching(session, target_timezone)

    # 2. Deadline Scanning
    deadline_alerts = await scan_upcoming_deadlines(session, reference_time)

    # 3. Dispatch deadline warnings
    alerts_dispatched = 0
    for alert in deadline_alerts:
        for u_id in alert["user_ids"]:
            # Send Webhook
            await dispatch_user_webhooks(
                user_id=u_id,
                event_type="scholarship.deadline_warning",
                payload={
                    "scholarship_id": str(alert["scholarship_id"]),
                    "title": alert["title"],
                    "days_remaining": alert["days_remaining"],
                    "deadline": alert["deadline"],
                    "bucket": alert["bucket"],
                },
                session=session,
            )

            # Send Telegram Alert
            msg = format_deadline_alert(
                scholarship_title=alert["title"],
                days_remaining=alert["days_remaining"],
                deadline_str=alert["deadline"],
                application_status="in_progress",
            )
            await send_telegram_message(chat_id=str(u_id), text=msg)
            alerts_dispatched += 1

    return {
        "matching": matching_summary,
        "deadline_alerts_count": len(deadline_alerts),
        "notifications_dispatched": alerts_dispatched,
    }
