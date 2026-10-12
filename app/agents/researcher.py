"""Researcher Agent: gathers verified school and department facts with 7-day caching."""
import re
import uuid
import ipaddress
from urllib.parse import urlsplit
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import httpx
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.logging import logger
from app.core.llm_gateway import sanitize_untrusted_content
from app.core.tracing import agent_span, tool_span
from app.db.models import Job, Scholarship
from app.jobs.queue import register_job_handler

# 7-day in-memory / persistent research cache store
_RESEARCH_CACHE: Dict[str, Dict[str, Any]] = {}
CACHE_TTL_DAYS = 7


def public_source_url(url: str) -> bool:
    """Reject obvious private destinations; redirects are never followed."""
    parsed = urlsplit(url)
    host = parsed.hostname or ""
    if parsed.scheme not in {"http", "https"} or parsed.username or parsed.password:
        return False
    if host.lower() in {"localhost", "metadata.google.internal"} or host.lower().endswith((".localhost", ".local", ".internal")):
        return False
    try:
        return ipaddress.ip_address(host).is_global
    except ValueError:
        return bool(host and "." in host)


class ResearchFact(BaseModel):
    fact_id: str
    category: str  # school, department, professor, priority
    claim: str
    source_url: str
    retrieved_at: str


class ResearcherInput(BaseModel):
    scholarship_id: uuid.UUID


class ResearcherOutput(BaseModel):
    scholarship_id: uuid.UUID
    school: str
    department: str
    programme_priorities: List[str]
    facts: List[ResearchFact]
    from_cache: bool


@agent_span("researcher", role="Institutional Researcher", goal="Gather verified institutional priorities")
async def run_researcher(scholarship_id: uuid.UUID, session: AsyncSession) -> ResearcherOutput:
    """Researches scholarship institution, department, and faculty priorities with strict source enforcement."""
    cache_key = str(scholarship_id)
    now = datetime.now(timezone.utc)

    # 1. Check 7-day cache
    if cache_key in _RESEARCH_CACHE:
        entry = _RESEARCH_CACHE[cache_key]
        cached_time = datetime.fromisoformat(entry["cached_at"])
        if now - cached_time < timedelta(days=CACHE_TTL_DAYS):
            return ResearcherOutput(
                scholarship_id=scholarship_id,
                school=entry["school"],
                department=entry["department"],
                programme_priorities=entry["programme_priorities"],
                facts=[ResearchFact.model_validate(f) for f in entry["facts"]],
                from_cache=True,
            )

    # 2. Load scholarship from database
    s = await session.get(Scholarship, scholarship_id)
    if not s:
        raise ValueError(f"Scholarship {scholarship_id} not found.")

    school_name = s.provider
    dept_name = ""
    base_url = s.application_url

    # 3. Live portal snippet extraction if reachable
    live_snippet: Optional[str] = None
    if public_source_url(base_url):
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
                res = await client.get(base_url)
                if res.status_code == 200:
                    raw_html = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", res.text[:2000], flags=re.I | re.S)
                    clean_text = re.sub(r"<[^>]+>", " ", raw_html)
                    clean_text = " ".join(clean_text.split())
                    suspicious = any(term in clean_text.lower() for term in (
                        "ignore previous", "system prompt", "api key", "login required", "sign in to continue",
                    ))
                    if len(clean_text) > 40 and not suspicious:
                        live_snippet = clean_text[:200]
        except httpx.HTTPError:
            logger.warning("Public institutional page could not be retrieved; no facts inferred.")

    # Sourced institutional facts
    candidate_facts: List[Dict[str, Any]] = []

    if live_snippet:
        candidate_facts.insert(0, {
            "fact_id": f"RF_{s.id.hex[:4]}_LIVE",
            "category": "portal_verified",
            "claim": live_snippet,
            "source_url": base_url,
            "retrieved_at": now.isoformat(),
        })

    # Rule per Section 8.2: "Every claim must carry a source. Unsourced claims are dropped before reaching the Drafter."
    verified_facts: List[ResearchFact] = []
    for cf in candidate_facts:
        if cf.get("source_url") and cf.get("claim"):
            # Sanitize untrusted content before storage
            cf["claim"] = sanitize_untrusted_content(cf["claim"]).replace("<untrusted_document_content>\n", "").replace("\n</untrusted_document_content>", "")
            verified_facts.append(ResearchFact.model_validate(cf))

    priorities: List[str] = []

    # Store in cache
    _RESEARCH_CACHE[cache_key] = {
        "cached_at": now.isoformat(),
        "school": school_name,
        "department": dept_name,
        "programme_priorities": priorities,
        "facts": [f.model_dump() for f in verified_facts],
    }

    return ResearcherOutput(
        scholarship_id=scholarship_id,
        school=school_name,
        department=dept_name,
        programme_priorities=priorities,
        facts=verified_facts,
        from_cache=False,
    )


@register_job_handler("researcher")
async def researcher_job_handler(job: Job, payload: Dict[str, Any], session: AsyncSession) -> Dict[str, Any]:
    """Queue worker handler for 'researcher' jobs."""
    inp = ResearcherInput.model_validate(payload)
    output = await run_researcher(inp.scholarship_id, session)
    return output.model_dump(mode="json")
