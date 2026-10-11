"""Profile Vault management endpoints."""
from typing import Annotated, Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user, get_request_id
from app.db.base import get_db_session
from app.db.models import Profile, User

router = APIRouter(prefix="/profile", tags=["Profile Vault"])


class ProfilePayload(BaseModel):
    personal_details: Dict[str, Any] = Field(default_factory=dict)
    education_history: List[Dict[str, Any]] = Field(default_factory=list)
    grades: Dict[str, Any] = Field(default_factory=dict)
    test_scores: Dict[str, Any] = Field(default_factory=dict)
    achievements: List[Dict[str, Any]] = Field(default_factory=list)
    financial_need_info: Dict[str, Any] = Field(default_factory=dict)
    target_countries: List[str] = Field(default_factory=list)
    target_fields_of_study: List[str] = Field(default_factory=list)


class ProfileResponse(ProfilePayload):
    id: str
    user_id: str
    completeness_score: float
    updated_at: str


def compute_completeness_score(payload: ProfilePayload) -> float:
    """Calculates profile completeness percentage (0.0 to 100.0)."""
    score = 0.0
    if payload.personal_details and len(payload.personal_details) > 0:
        score += 15.0
    if payload.education_history and len(payload.education_history) > 0:
        score += 20.0
    if payload.grades and len(payload.grades) > 0:
        score += 15.0
    if payload.achievements and len(payload.achievements) > 0:
        score += 20.0
    if payload.target_countries and len(payload.target_countries) > 0:
        score += 10.0
    if payload.target_fields_of_study and len(payload.target_fields_of_study) > 0:
        score += 10.0
    if payload.financial_need_info and len(payload.financial_need_info) > 0:
        score += 10.0
    return min(100.0, round(score, 1))


@router.get("", response_model=ProfileResponse)
async def get_profile(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProfileResponse:
    """Retrieves the authenticated user's Profile Vault."""
    stmt = select(Profile).where(Profile.user_id == user.id)
    profile = (await db.execute(stmt)).scalar_one_or_none()

    if not profile:
        # Create empty profile if none exists
        profile = Profile(
            user_id=user.id,
            personal_details={},
            education_history=[],
            grades={},
            test_scores={},
            achievements=[],
            financial_need_info={},
            target_countries=[],
            target_fields_of_study=[],
            completeness_score=0.0,
        )
        db.add(profile)
        await db.commit()
        await db.refresh(profile)

    return ProfileResponse(
        id=str(profile.id),
        user_id=str(profile.user_id),
        personal_details=profile.personal_details or {},
        education_history=profile.education_history or [],
        grades=profile.grades or {},
        test_scores=profile.test_scores or {},
        achievements=profile.achievements or [],
        financial_need_info=profile.financial_need_info or {},
        target_countries=profile.target_countries or [],
        target_fields_of_study=profile.target_fields_of_study or [],
        completeness_score=profile.completeness_score,
        updated_at=profile.updated_at.isoformat(),
    )


@router.put("", response_model=ProfileResponse)
async def update_profile(
    payload: ProfilePayload,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProfileResponse:
    """Updates the authenticated user's Profile Vault and recalculates completeness score."""
    stmt = select(Profile).where(Profile.user_id == user.id)
    profile = (await db.execute(stmt)).scalar_one_or_none()

    score = compute_completeness_score(payload)

    if not profile:
        profile = Profile(
            user_id=user.id,
            personal_details=payload.personal_details,
            education_history=payload.education_history,
            grades=payload.grades,
            test_scores=payload.test_scores,
            achievements=payload.achievements,
            financial_need_info=payload.financial_need_info,
            target_countries=payload.target_countries,
            target_fields_of_study=payload.target_fields_of_study,
            completeness_score=score,
        )
        db.add(profile)
    else:
        profile.personal_details = payload.personal_details
        profile.education_history = payload.education_history
        profile.grades = payload.grades
        profile.test_scores = payload.test_scores
        profile.achievements = payload.achievements
        profile.financial_need_info = payload.financial_need_info
        profile.target_countries = payload.target_countries
        profile.target_fields_of_study = payload.target_fields_of_study
        profile.completeness_score = score

    await db.commit()
    await db.refresh(profile)

    return ProfileResponse(
        id=str(profile.id),
        user_id=str(profile.user_id),
        personal_details=profile.personal_details or {},
        education_history=profile.education_history or [],
        grades=profile.grades or {},
        test_scores=profile.test_scores or {},
        achievements=profile.achievements or [],
        financial_need_info=profile.financial_need_info or {},
        target_countries=profile.target_countries or [],
        target_fields_of_study=profile.target_fields_of_study or [],
        completeness_score=profile.completeness_score,
        updated_at=profile.updated_at.isoformat(),
    )
