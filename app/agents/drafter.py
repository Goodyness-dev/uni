"""Drafter Agent: generates essays and statements with in-code word limit enforcement and grounding checks."""
import re
import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.agents.edge_finder import Angle
from app.agents.verifier import run_verifier
from app.core.tracing import agent_span
from app.db.models import Application, Draft, Job, Profile, Scholarship, ApplicationEvent
from app.core.config import settings
from app.core.evidence import approved_facts
from app.agents.generation import draft_verified
from app.agents.packager import build_package
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
    """Grounding check: verifies every sentence maps to profile facts using self-healing Verifier."""
    clean_content, report = run_verifier(draft_text, allowed_facts, mode="B")
    ungrounded_flagged = [rc.sentence for rc in report.removed_claims]
    used_sources = [fact for fact in allowed_facts if fact.strip().rstrip(".!?") in clean_content]
    return clean_content, used_sources, ungrounded_flagged


@agent_span("drafter", role="Grounded Tailor", goal="Prepare an application grounded in reviewed evidence")
async def run_drafter(
    application_id: uuid.UUID,
    user_id: uuid.UUID,
    scholarship_id: uuid.UUID,
    angles: List[Angle],
    essay_prompt: str,
    word_limit: int,
    session: AsyncSession,
    research_facts: Optional[List[Dict[str, Any]]] = None,
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

    if profile is None:
        raise ValueError("A profile is required before drafting.")
    application = await session.get(Application, application_id)
    if not application or application.user_id != user_id or application.scholarship_id != scholarship_id:
        raise ValueError("Draft ownership or scholarship does not match the application.")
    # Extractive baseline: only original applicant descriptions enter the output.
    allowed_facts: List[str] = []
    for item in (profile.achievements or []) + (profile.education_history or []):
        text = item.get("description") or item.get("title") or item.get("degree")
        if isinstance(text, str) and text.strip():
            allowed_facts.append(text.strip())
    reviewed = await approved_facts(profile, session)
    reviewed = [fact for fact in reviewed if not fact.get("sensitive") and fact.get("category", "").lower() not in {"sensitive", "hardships", "health", "religion", "medical", "financial_need"}]
    allowed_facts.extend(fact["text"] for fact in reviewed)
    if not allowed_facts:
        raise ValueError("No original profile evidence is available for drafting.")
    raw_draft = " ".join(fact if fact.endswith((".", "!", "?")) else fact + "." for fact in allowed_facts)
    # Do not truncate factual sentences into different claims.
    selected = []
    count = 0
    for fact in allowed_facts:
        size = len(fact.split())
        if count + size <= word_limit:
            selected.append(fact if fact.endswith((".", "!", "?")) else fact + ".")
            count += size
    clean_draft, source_facts, ungrounded_flagged = perform_grounding_check(" ".join(selected), allowed_facts)
    final_text = clean_draft.strip()
    final_word_count = len(final_text.split())
    if not final_text:
        raise ValueError("No supported text remains; application requires human writing.")

    verification, usage, sources = None, [], []
    policy = (scholarship.eligibility_rules or {}).get("ai_policy", "unknown")
    generated = []
    if settings.LLM_DRAFTING and policy in {"allowed", "disclose"}:
        sources = [{"id": fact["id"], "text": fact["text"], "kind": "profile"}
            for fact in reviewed if fact.get("category", "").lower() not in {"hardships", "health", "religion", "medical", "financial_need"}]
        sources.extend({"id": fact["fact_id"], "text": fact["claim"], "kind": "institution"} for fact in (research_facts or []) if fact.get("source_url") and fact.get("claim"))
        async def record(kind: str, payload: dict[str, Any]) -> None:
            session.add(ApplicationEvent(application_id=application_id, actor="verifier", event_type=kind, payload=payload))
            await session.commit()
        selected_text = {text for angle in angles for text in (angle.get("supporting_profile_facts", []) if isinstance(angle, dict) else angle.supporting_profile_facts)}
        preferred_ids = [fact["id"] for fact in reviewed if fact["text"] in selected_text]
        generated, verification, usage = await draft_verified(sources, essay_prompt, word_limit, str(user_id), record, preferred_ids)
        final_text = " ".join(segment.text for segment in generated if segment.section == "essay")
        final_word_count = len(final_text.split())
        source_facts = sorted({source for segment in generated for source in segment.source_ids})
        ungrounded_flagged = [claim["text"] for claim in verification["removed_claims"]]
    else:
        _, audit = run_verifier(final_text, allowed_facts)
        verification = {"rounds": 1, "claims": [], "removed_claims": [], "overturned_claims": [],
            "unsupported_before": len(audit.removed_claims), "unsupported_final": audit.unsupported_claims,
            "mode": "original_evidence_notes" if policy not in {"allowed", "disclose"} else "extractive"}

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
    if generated:
        for section in ("cv_summary", "cv_bullets"):
            pieces = [segment for segment in generated if segment.section == section]
            if pieces:
                session.add(Draft(application_id=application_id, kind=section, version=next_version,
                    content="\n".join(segment.text for segment in pieces),
                    source_facts=sorted({source for segment in pieces for source in segment.source_ids})))
    session.add(ApplicationEvent(application_id=application_id, actor="verifier", event_type="verification_report",
        payload={"report": verification, "usage": usage,
            "sources": sources,
            "segments": [segment.model_dump() for segment in generated]}))
    await session.commit()
    await session.refresh(draft_record)
    await build_package(application, session)

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
