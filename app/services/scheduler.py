"""Production scheduler: daily discovery/matching loop per user timezone and proactive deadline alerts."""
import uuid
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.agents.matcher import run_matcher
from app.core.logging import logger
from app.db.models import Application, Match, Profile, Scholarship, User
from app.integrations.telegram import format_deadline_alert, send_telegram_message
from app.integrations.webhooks import dispatch_user_webhooks
from app.jobs.queue import enqueue_job, get_redis_client, register_job_handler
from app.db.models import Job


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
    if target_timezone is not None:
        stmt = stmt.where(User.timezone == target_timezone)
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
    logger.info(f"Starting autonomous daily scheduler cycle (target_timezone={target_timezone})")

    # 1. Matching
    matching_summary = await run_daily_discovery_and_matching(session, target_timezone)

    # 2. Deadline Scanning
    deadline_alerts = await scan_upcoming_deadlines(session, reference_time)

    # 3. Dispatch deadline warnings
    alerts_dispatched = 0
    for alert in deadline_alerts:
        for u_id in alert["user_ids"]:
            user_obj = await session.get(User, u_id)
            if not user_obj:
                continue
            if user_obj.status != "active":
                continue

            if target_timezone is not None and user_obj.timezone != target_timezone:
                continue
            client = await get_redis_client()
            key = f"scholarpilot:deadline:{u_id}:{alert['scholarship_id']}:{alert['deadline']}:{alert['bucket']}"
            if client and not await client.set(key, "sending", nx=True, ex=60):
                continue

            # Send Webhook
            deliveries = await dispatch_user_webhooks(
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

            # Send Telegram Alert if user has configured telegram_chat_id
            delivered = any(result.get("success") for result in deliveries)
            if user_obj.telegram_chat_id:
                msg = format_deadline_alert(
                    scholarship_title=alert["title"],
                    days_remaining=alert["days_remaining"],
                    deadline_str=alert["deadline"],
                    application_status="in_progress",
                )
                result = await send_telegram_message(chat_id=user_obj.telegram_chat_id, text=msg)
                delivered = delivered or (bool(result.get("ok")) if isinstance(result, dict) else bool(result))

            if delivered:
                alerts_dispatched += 1
                if client:
                    await client.set(key, "delivered", ex=1728000)
            elif client:
                await client.delete(key)

    return {
        "matching": matching_summary,
        "deadline_alerts_count": len(deadline_alerts),
        "notifications_dispatched": alerts_dispatched,
    }


async def schedule_daily_cycles(session: AsyncSession, reference_time: Optional[datetime] = None) -> int:
    """Enqueue one catalog matching cycle per timezone/local date across workers."""
    now = reference_time or datetime.now(timezone.utc)
    client = await get_redis_client()
    if client is None:
        logger.warning("Daily scheduling requires Redis deduplication; cycle not enqueued.")
        return 0
    zones = (await session.execute(select(User.timezone).where(User.status == "active").distinct())).scalars().all()
    count = 0
    for zone in zones:
        try:
            tz = ZoneInfo(zone)
        except ZoneInfoNotFoundError:
            if zone == "Africa/Lagos":
                tz = timezone(timedelta(hours=1))
            elif zone in ("UTC", "GMT"):
                tz = timezone.utc
            else:
                logger.warning("Invalid stored timezone; daily cycle skipped.")
                continue
        day = now.astimezone(tz).date().isoformat()
        key = f"scholarpilot:daily:{zone}:{day}"
        if await client.set(key, "scheduled", nx=True, ex=172800):
            try:
                await enqueue_job("daily_scheduler", {"timezone": zone}, session=session)
            except Exception:
                await client.delete(key)
                raise
            count += 1
    return count


@register_job_handler("daily_scheduler")
async def daily_scheduler_job(job: Job, payload: Dict[str, Any], session: AsyncSession) -> Dict[str, Any]:
    """Worker entry for the scheduled catalog matching and deadline cycle."""
    return await run_daily_scheduler_cycle(session, target_timezone=payload.get("timezone"))
