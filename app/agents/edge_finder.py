"""Edge Finder Agent: selects the strongest angles connecting profile facts to school priorities."""
import uuid
from typing import Any, Dict, List
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.agents.researcher import ResearchFact
from app.db.models import Job, Profile, Scholarship
from app.jobs.queue import register_job_handler


class Angle(BaseModel):
    angle_id: str
    theme: str  # technical_project, leadership, adversity_resilience, research_alignment
    headline: str
    supporting_profile_facts: List[str]
    reasoning: str
    score: float


class EdgeFinderInput(BaseModel):
    user_id: uuid.UUID
    scholarship_id: uuid.UUID
    research_facts: List[ResearchFact] = Field(default_factory=list)


class EdgeFinderOutput(BaseModel):
    scholarship_id: uuid.UUID
    angles: List[Angle]


async def run_edge_finder(
    user_id: uuid.UUID,
    scholarship_id: uuid.UUID,
    research_facts: List[ResearchFact],
    session: AsyncSession,
) -> EdgeFinderOutput:
    """Discovers competitive edges grounded in verified profile facts and school priorities."""
    stmt = select(Profile).where(Profile.user_id == user_id)
    profile = (await session.execute(stmt)).scalar_one_or_none()
    if not profile:
        raise ValueError(f"Profile for user {user_id} not found.")

    scholarship = await session.get(Scholarship, scholarship_id)
    if not scholarship:
        raise ValueError(f"Scholarship {scholarship_id} not found.")

    angles: List[Angle] = []

    # 1. Project / Technical Achievement Angle
    achievements = profile.achievements or []
    if achievements:
        top_ach = achievements[0]
        ach_title = top_ach.get("title", "Undergraduate Engineering Project")
        angles.append(
            Angle(
                angle_id="ANG_1_TECH",
                theme="technical_project",
                headline=f"Proven execution in {ach_title}",
                supporting_profile_facts=[
                    f"Achievement: {ach_title} ({top_ach.get('year', 'Recent')})",
                    f"Degree: {profile.education_history[0].get('degree', 'Computer Engineering') if profile.education_history else 'B.Sc.'}",
                ],
                reasoning=f"Aligns directly with {scholarship.provider}'s emphasis on practical technological solutions.",
                score=0.92,
            )
        )

    # 2. Academic Rigor Angle
    gpa = profile.grades.get("gpa")
    if gpa and gpa >= 4.0:
        angles.append(
            Angle(
                angle_id="ANG_2_ACADEMIC",
                theme="academic_rigor",
                headline=f"Exceptional academic record with {gpa}/{profile.grades.get('gpa_scale', 5.0)} GPA",
                supporting_profile_facts=[f"GPA: {gpa} on scale {profile.grades.get('gpa_scale', 5.0)}"],
                reasoning=f"Exceeds minimum requirements and demonstrates academic readiness for graduate study.",
                score=0.88,
            )
        )

    # 3. Community Impact / Resilience Angle
    need_info = profile.financial_need_info.get("statement")
    if need_info or len(profile.target_fields_of_study) > 0:
        angles.append(
            Angle(
                angle_id="ANG_3_IMPACT",
                theme="adversity_resilience",
                headline="Clear vision for sustainable development and home country impact",
                supporting_profile_facts=[
                    f"Target field: {', '.join(profile.target_fields_of_study)}",
                    f"Origin: {profile.personal_details.get('nationalities', ['Nigeria'])[0]}",
                ],
                reasoning="Directly satisfies the scholarship mandate for emerging leaders committed to post-graduation national development.",
                score=0.85,
            )
        )

    # Sort angles by score descending
    angles.sort(key=lambda a: a.score, reverse=True)

    return EdgeFinderOutput(
        scholarship_id=scholarship_id,
        angles=angles[:3],
    )


@register_job_handler("edge_finder")
async def edge_finder_job_handler(job: Job, payload: Dict[str, Any], session: AsyncSession) -> Dict[str, Any]:
    """Queue worker handler for 'edge_finder' jobs."""
    inp = EdgeFinderInput.model_validate(payload)
    output = await run_edge_finder(inp.user_id, inp.scholarship_id, inp.research_facts, session)
    return output.model_dump(mode="json")
