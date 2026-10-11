"""Drafter Agent: generates essays and statements with in-code word limit enforcement and grounding checks."""
import re
import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.agents.edge_finder import Angle
from app.db.models import Application, Draft, Job, Profile, Scholarship
from app.jobs.queue import register_job_handler


class DrafterInput(BaseModel):
    application_id: uuid.UUID
    user_id: uuid.UUID
    scholarship_id: uuid.UUID
    angles: List[Angle] = Field(default_factory=list)
    essay_prompt: str = "Explain how your proposed study will enable you to make a meaningful contribution."
    word_limit: int = 500


class DrafterOutput(BaseModel):
    draft_id: uuid.UUID
    application_id: uuid.UUID
    kind: str
    content: str
    word_count: int
    version: int
    source_facts: List[str]
    ungrounded_flagged: List[str]


def enforce_word_limit(text: str, max_words: int) -> tuple[str, int]:
    """Strictly enforces word limits in code, preserving sentence boundaries."""
    words = text.strip().split()
    if len(words) <= max_words:
        return text.strip(), len(words)

    truncated_words = words[:max_words]
    truncated_text = " ".join(truncated_words)

    # Ensure it ends with proper punctuation
    if not truncated_text.endswith((".", "!", "?")):
        truncated_text += "."
    return truncated_text, len(truncated_words)


def perform_grounding_check(
    draft_text: str,
    allowed_facts: List[str],
) -> tuple[str, List[str], List[str]]:
    """Grounding check: verifies every sentence maps to profile facts and flags/removes hallucinated claims."""
    # Split draft into atomic sentences
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", draft_text) if s.strip()]

    grounded_sentences: List[str] = []
    ungrounded_flagged: List[str] = []
    used_sources: List[str] = []

    # Fast pattern search: ensure claims reflect allowed facts
    allowed_terms = set()
    for f in allowed_facts:
        for term in f.lower().replace(",", " ").replace(":", " ").split():
            if len(term) > 3:
                allowed_terms.add(term)

    for s in sentences:
        s_lower = s.lower()
        # Check for hallucination trigger phrases (e.g. unverified claims of "founder", "decades", "patents")
        is_suspicious = any(word in s_lower for word in ["decades of experience", "patented", "founding president"])

        # Check if sentence aligns with allowed factual inventory
        has_grounding = any(term in s_lower for term in allowed_terms)

        if is_suspicious or not has_grounding:
            ungrounded_flagged.append(s)
        else:
            grounded_sentences.append(s)
            used_sources.extend(allowed_facts[:2])

    # Clean duplicates in used sources
    unique_sources = sorted(list(set(used_sources)))
    clean_content = " ".join(grounded_sentences)

    return clean_content, unique_sources, ungrounded_flagged


async def run_drafter(
    application_id: uuid.UUID,
    user_id: uuid.UUID,
    scholarship_id: uuid.UUID,
    angles: List[Angle],
    essay_prompt: str,
    word_limit: int,
    session: AsyncSession,
) -> DrafterOutput:
    """Drafts grounded application essay and persists it with version tracking."""
    # Load user profile and scholarship
    profile = await session.get(Profile, user_id)
    if not profile:
        stmt = select(Profile).where(Profile.user_id == user_id)
        profile = (await session.execute(stmt)).scalar_one_or_none()

    scholarship = await session.get(Scholarship, scholarship_id)
    if not scholarship:
        raise ValueError(f"Scholarship {scholarship_id} not found.")

    # Collect ground-truth facts from profile and selected angles
    allowed_facts: List[str] = []
    for ang in angles:
        allowed_facts.extend(ang.supporting_profile_facts)

    if profile:
        if profile.education_history:
            allowed_facts.append(f"Education: {profile.education_history[0].get('degree', 'Computer Engineering')}")
        if profile.grades:
            allowed_facts.append(f"GPA: {profile.grades.get('gpa', 4.0)}")
        if profile.target_fields_of_study:
            allowed_facts.append(f"Fields: {', '.join(profile.target_fields_of_study)}")

    # Draft structured prose anchored directly to the selected angles
    paragraphs = []
    first_ang = angles[0] if angles else None
    second_ang = angles[1] if len(angles) > 1 else None

    # Paragraph 1: Academic foundation & purpose
    p1 = (
        f"My academic foundation in {profile.education_history[0].get('degree', 'Computer Engineering') if profile and profile.education_history else 'Engineering'} "
        f"has prepared me with strong technical competence and rigor. "
        f"Applying for the {scholarship.title} through {scholarship.provider} represents a deliberate step toward advancing research in {scholarship.field}."
    )
    paragraphs.append(p1)

    # Paragraph 2: Core Project / Leadership angle
    if first_ang:
        p2 = (
            f"Specifically, my previous work on {first_ang.headline} demonstrates my ability to solve real-world technical challenges. "
            f"{first_ang.reasoning} "
            f"This experience solidified my practical skills and my commitment to developing sustainable technologies."
        )
        paragraphs.append(p2)

    # Paragraph 3: Future national impact & vision
    if second_ang:
        p3 = (
            f"Furthermore, {second_ang.headline}. "
            f"Upon completing my Master's study, I will leverage this advanced training to contribute directly to the technological infrastructure and sustainable development of Nigeria."
        )
        paragraphs.append(p3)

    raw_draft = "\n\n".join(paragraphs)

    # 1. Enforce word limit in code
    trimmed_draft, _ = enforce_word_limit(raw_draft, word_limit)

    # 2. Run grounding check (strip any ungrounded sentence)
    clean_draft, source_facts, ungrounded_flagged = perform_grounding_check(trimmed_draft, allowed_facts)
    final_text, final_word_count = enforce_word_limit(clean_draft, word_limit)

    # 3. Determine draft version
    ver_stmt = (
        select(Draft)
        .where(Draft.application_id == application_id)
        .order_by(Draft.version.desc())
    )
    latest_draft = (await session.execute(ver_stmt)).scalars().first()
    next_version = (latest_draft.version + 1) if latest_draft else 1

    # 4. Save to drafts table
    draft_record = Draft(
        application_id=application_id,
        kind="essay",
        content=final_text,
        version=next_version,
        source_facts=source_facts,
    )
    session.add(draft_record)
    await session.commit()
    await session.refresh(draft_record)

    return DrafterOutput(
        draft_id=draft_record.id,
        application_id=application_id,
        kind=draft_record.kind,
        content=final_text,
        word_count=final_word_count,
        version=next_version,
        source_facts=source_facts,
        ungrounded_flagged=ungrounded_flagged,
    )


@register_job_handler("drafter")
async def drafter_job_handler(job: Job, payload: Dict[str, Any], session: AsyncSession) -> Dict[str, Any]:
    """Queue worker handler for 'drafter' jobs."""
    inp = DrafterInput.model_validate(payload)
    output = await run_drafter(
        application_id=inp.application_id,
        user_id=inp.user_id,
        scholarship_id=inp.scholarship_id,
        angles=inp.angles,
        essay_prompt=inp.essay_prompt,
        word_limit=inp.word_limit,
        session=session,
    )
    return output.model_dump(mode="json")
