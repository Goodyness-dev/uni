"""Edge Finder Agent: selects the strongest angles connecting profile facts to school priorities."""
import uuid
from typing import Any, Dict, List, Optional
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


from app.core.tracing import agent_span


def _get_rf(facts: List[Any], category: str) -> Optional[str]:
    for rf in facts:
        cat = getattr(rf, "category", None) or (rf.get("category") if isinstance(rf, dict) else None)
        if cat == category:
            return getattr(rf, "claim", None) or (rf.get("claim") if isinstance(rf, dict) else None)
    return None


@agent_span("edge_finder", role="Competitive Edge Finder", goal="Ground competitive edges against research facts")
async def run_edge_finder(
    user_id: uuid.UUID,
    scholarship_id: uuid.UUID,
    research_facts: List[Any],
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
    evidence = []
    for achievement in profile.achievements or []:
        text = achievement.get("description") or achievement.get("title")
        if isinstance(text, str) and text.strip():
            evidence.append(text.strip())
    for education in profile.education_history or []:
        degree = education.get("degree")
        if isinstance(degree, str) and degree.strip():
            evidence.append(degree.strip())
    research_text = " ".join(
        (rf.get("claim", "") if isinstance(rf, dict) else rf.claim)
        for rf in research_facts
    ).lower()
    for index, fact in enumerate(evidence[:3]):
        terms = {word.lower() for word in fact.split() if len(word) > 3}
        overlap = sum(word in research_text for word in terms)
        angles.append(Angle(
            angle_id=f"ANG_{index + 1}", theme="profile_evidence", headline=fact,
            supporting_profile_facts=[fact],
            reasoning="Literal profile evidence; institutional alignment is not inferred.",
            score=overlap / len(terms) if terms else 0.0,
        ))
    return EdgeFinderOutput(scholarship_id=scholarship_id, angles=angles)


@register_job_handler("edge_finder")
async def edge_finder_job_handler(job: Job, payload: Dict[str, Any], session: AsyncSession) -> Dict[str, Any]:
    """Queue worker handler for 'edge_finder' jobs."""
    inp = EdgeFinderInput.model_validate(payload)
    output = await run_edge_finder(inp.user_id, inp.scholarship_id, inp.research_facts, session)
    return output.model_dump(mode="json")
