"""Ranked scholarship matching and scoring endpoints."""
import uuid
from datetime import datetime, timezone
from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user
from app.db.base import get_db_session
from app.db.models import Match, Profile, Scholarship, User

router = APIRouter(prefix="/matches", tags=["Matches"])


class MatchResponse(BaseModel):
    id: str
    scholarship_id: str
    scholarship_title: str
    scholarship_country: str
    scholarship_amount: float
    deadline: Optional[str] = None
    fit_score: float
    urgency_score: float
    reasons: List[str]
    created_at: str


def evaluate_eligibility_and_fit(profile: Profile, scholarship: Scholarship) -> Optional[tuple[float, float, List[str]]]:
    """Deterministic eligibility check and fit scoring per Section 8.1."""
    rules = scholarship.eligibility_rules or {}
    reasons: List[str] = []

    # 1. Deadline check
    now = datetime.now(timezone.utc)
    urgency = 50.0
    if scholarship.deadline:
        deadline = scholarship.deadline
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)
        if deadline < now:
            return None  # Expired
        days_left = max(0, (deadline - now).days)
        if days_left <= 7:
            urgency = 95.0
            reasons.append(f"Urgent: Deadline in {days_left} days")
        elif days_left <= 30:
            urgency = 80.0
            reasons.append(f"Deadline approaching in {days_left} days")
        else:
            urgency = 40.0
            reasons.append(f"Deadline in {days_left} days")

    # 2. Level check
    target_level = "masters"  # Default assumption for graduate study
    if scholarship.level.lower() != target_level.lower():
        # Soft match or check profile
        pass
    else:
        reasons.append(f"Target degree level matches {scholarship.level.title()}")

    # 3. Country / Nationality check
    eligible_nats = rules.get("eligible_nationalities", [])
    user_nats = profile.personal_details.get("nationalities") or []
    if not user_nats and profile.personal_details.get("citizenship"):
        user_nats = [profile.personal_details["citizenship"]]
    if eligible_nats:
        matched_nat = any(nat.lower() in [n.lower() for n in eligible_nats] for nat in user_nats)
        if not matched_nat:
            return None  # Hard ineligible
        reasons.append(f"Eligible for {', '.join(user_nats)} applicants")

    # 4. GPA check
    min_gpa = rules.get("min_gpa", 0.0)
    user_gpa = profile.grades.get("gpa")
    if min_gpa > 0:
        scale = profile.grades.get("gpa_scale")
        required_scale = rules.get("gpa_scale")
        if not isinstance(user_gpa, (int, float)) or not scale or not required_scale:
            return None
        if user_gpa / scale < min_gpa / required_scale:
            return None
    elif min_gpa > 0:
        reasons.append(f"GPA {user_gpa} meets minimum requirement ({min_gpa})")

    # 5. Field of study fit scoring
    fit_score = 70.0
    user_fields = [f.lower() for f in profile.target_fields_of_study]
    schol_fields = [f.lower() for f in rules.get("fields", [scholarship.field])]

    field_match = any(any(uf in sf or sf in uf for sf in schol_fields) for uf in user_fields)
    if field_match:
        fit_score += 20.0
        reasons.append(f"Field of study aligns with {scholarship.field}")
    else:
        fit_score += 5.0
        reasons.append("Related interdisciplinary opportunity")

    # Add achievement boost
    achievements_count = len(profile.achievements or [])
    if achievements_count >= 2:
        fit_score += 10.0
        reasons.append(f"Strong profile with {achievements_count} recorded achievements/awards")

    final_fit = min(100.0, round(fit_score, 1))
    return final_fit, urgency, reasons


@router.post("/refresh", response_model=List[MatchResponse])
async def refresh_matches(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> List[MatchResponse]:
    """Runs deterministic eligibility filtering and fit scoring against active catalog."""
    # Load user profile
    stmt = select(Profile).where(Profile.user_id == user.id)
    profile = (await db.execute(stmt)).scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=400, detail="A profile is required before matching.")

    # Load active scholarships
    schol_stmt = select(Scholarship).where(Scholarship.status == "active")
    scholarships = (await db.execute(schol_stmt)).scalars().all()

    # Clear existing matches for fresh refresh
    del_stmt = select(Match).where(Match.user_id == user.id)
    existing_matches = (await db.execute(del_stmt)).scalars().all()
    for em in existing_matches:
        await db.delete(em)

    new_matches: List[Match] = []
    for s in scholarships:
        res = evaluate_eligibility_and_fit(profile, s)
        if res is not None:
            fit_score, urgency_score, reasons = res
            match_row = Match(
                user_id=user.id,
                scholarship_id=s.id,
                fit_score=fit_score,
                urgency_score=urgency_score,
                reasons=reasons,
            )
            db.add(match_row)
            new_matches.append(match_row)

    await db.commit()

    # Re-fetch with scholarship details
    fetch_stmt = (
        select(Match, Scholarship)
        .join(Scholarship, Match.scholarship_id == Scholarship.id)
        .where(Match.user_id == user.id)
        .order_by(Match.fit_score.desc())
    )
    rows = (await db.execute(fetch_stmt)).all()

    return [
        MatchResponse(
            id=str(m.id),
            scholarship_id=str(s.id),
            scholarship_title=s.title,
            scholarship_country=s.country,
            scholarship_amount=s.amount,
            deadline=s.deadline.isoformat() if s.deadline else None,
            fit_score=m.fit_score,
            urgency_score=m.urgency_score,
            reasons=m.reasons,
            created_at=m.created_at.isoformat(),
        )
        for m, s in rows
    ]


@router.get("", response_model=List[MatchResponse])
async def list_matches(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> List[MatchResponse]:
    """Retrieves ranked matches for the current user."""
    stmt = (
        select(Match, Scholarship)
        .join(Scholarship, Match.scholarship_id == Scholarship.id)
        .where(Match.user_id == user.id)
        .order_by(Match.fit_score.desc())
    )
    rows = (await db.execute(stmt)).all()

    return [
        MatchResponse(
            id=str(m.id),
            scholarship_id=str(s.id),
            scholarship_title=s.title,
            scholarship_country=s.country,
            scholarship_amount=s.amount,
            deadline=s.deadline.isoformat() if s.deadline else None,
            fit_score=m.fit_score,
            urgency_score=m.urgency_score,
            reasons=m.reasons,
            created_at=m.created_at.isoformat(),
        )
        for m, s in rows
    ]
