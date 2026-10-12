"""Matcher Agent: evaluates eligibility, calculates fit scores, and stores ranked matches."""
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.v1.matches import evaluate_eligibility_and_fit
from app.db.models import Job, Match, Profile, Scholarship
from app.jobs.queue import register_job_handler
from app.core.tracing import agent_span


class MatcherInput(BaseModel):
    user_id: uuid.UUID


class MatchItem(BaseModel):
    match_id: uuid.UUID
    scholarship_id: uuid.UUID
    scholarship_title: str
    fit_score: float
    urgency_score: float
    reasons: List[str]


class MatcherOutput(BaseModel):
    user_id: uuid.UUID
    total_evaluated: int
    matches: List[MatchItem]


@agent_span("matcher", role="Eligibility Matcher", goal="Filter catalog against supplied eligibility evidence")
async def run_matcher(user_id: uuid.UUID, session: AsyncSession) -> MatcherOutput:
    """Executes matching logic against all active catalog scholarships."""
    stmt = select(Profile).where(Profile.user_id == user_id)
    profile = (await session.execute(stmt)).scalar_one_or_none()
    if not profile:
        raise ValueError(f"Profile for user {user_id} not found.")

    schol_stmt = select(Scholarship).where(Scholarship.status == "active")
    scholarships = (await session.execute(schol_stmt)).scalars().all()

    # Clear prior matches for user
    del_stmt = select(Match).where(Match.user_id == user_id)
    old_matches = (await session.execute(del_stmt)).scalars().all()
    for om in old_matches:
        await session.delete(om)

    matched_items: List[MatchItem] = []
    for s in scholarships:
        res = evaluate_eligibility_and_fit(profile, s)
        if res is not None:
            fit_score, urgency_score, reasons = res
            match_row = Match(
                user_id=user_id,
                scholarship_id=s.id,
                fit_score=fit_score,
                urgency_score=urgency_score,
                reasons=reasons,
            )
            session.add(match_row)
            await session.flush()
            matched_items.append(
                MatchItem(
                    match_id=match_row.id,
                    scholarship_id=s.id,
                    scholarship_title=s.title,
                    fit_score=fit_score,
                    urgency_score=urgency_score,
                    reasons=reasons,
                )
            )

    await session.commit()
    matched_items.sort(key=lambda m: m.fit_score, reverse=True)

    return MatcherOutput(
        user_id=user_id,
        total_evaluated=len(scholarships),
        matches=matched_items,
    )


@register_job_handler("matcher")
async def matcher_job_handler(job: Job, payload: Dict[str, Any], session: AsyncSession) -> Dict[str, Any]:
    """Queue worker handler for 'matcher' jobs."""
    inp = MatcherInput.model_validate(payload)
    output = await run_matcher(inp.user_id, session)
    return output.model_dump(mode="json")
