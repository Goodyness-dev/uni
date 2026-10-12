"""Researcher Agent: retrieves literal official text with six-hour durable snapshots."""
import re
import uuid
import ipaddress
from urllib.parse import urlsplit
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import httpx
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.services.public_pages import parse_page, crawl_sources
from app.services.discovery import source_config
from app.core.logging import logger
from app.core.config import settings
from app.core.public_fetch import fetch_public_text
from app.core.llm_gateway import sanitize_untrusted_content
from app.core.tracing import agent_span, tool_span
from app.core.runtime import is_demo_portal
from app.db.models import Job, Scholarship
from app.jobs.queue import register_job_handler



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


@agent_span("researcher", role="Institutional Researcher", goal="Cross-check official institutional pages with durable provenance")
async def run_researcher(scholarship_id: uuid.UUID, session: AsyncSession,
    live_research: bool | None = None, force: bool = False) -> ResearcherOutput:
    scholarship = await session.get(Scholarship, scholarship_id)
    if scholarship is None:
        raise ValueError("Scholarship not found.")
    enabled = settings.LIVE_RESEARCH and live_research is not False
    url = scholarship.application_url
    owned = is_demo_portal(url) and "/portal/apply/" in url
    facts = []
    cached = False
    if owned:
        about = url.replace("/portal/apply/", "/portal/about/")
        snapshots = (await session.execute(select(Job).where(Job.type == "research_snapshot",
            Job.payload["url"].as_string() == about).order_by(Job.created_at.desc()).limit(1))).scalars().all()
        if snapshots and not force and datetime.now(timezone.utc) - datetime.fromisoformat(snapshots[0].payload["retrieved_at"]) < timedelta(hours=6):
            pages = [{**snapshots[0].payload, "from_cache": True}]
        else:
            async with httpx.AsyncClient(timeout=10, follow_redirects=False, trust_env=False) as client:
                response = await client.get(about)
                response.raise_for_status()
            page = parse_page(response.text[:200000], about)
            session.add(Job(type="research_snapshot", status="completed", payload=page, attempts=1))
            await session.commit()
            pages = [{**page, "from_cache": False}]
    elif enabled:
        config = source_config(scholarship)
        urls = config.get("urls", [url]) + config.get("university_urls", [])
        hosts = set(config.get("allowed_hosts", [urlsplit(url).hostname]))
        pages = await crawl_sources(urls, hosts, session, force=force)
    else:
        pages = []
    for page in pages:
        if not page.get("text") or page.get("blocker"):
            continue
        text = sanitize_untrusted_content(page["text"]).replace("<untrusted_document_content>\n", "").replace("\n</untrusted_document_content>", "")
        digest = page["sha256"][:10]
        snippet = text[:2200]
        facts.append(ResearchFact(fact_id="RF_" + digest, category="portal_verified" if owned else "official_source",
            claim=snippet, source_url=page["url"], retrieved_at=page["retrieved_at"]))
        cached = cached or page.get("from_cache", False)
    return ResearcherOutput(scholarship_id=scholarship.id, school=scholarship.provider, department="",
        programme_priorities=[], facts=facts, from_cache=cached)


@register_job_handler("researcher")
async def researcher_job_handler(job: Job, payload: Dict[str, Any], session: AsyncSession) -> Dict[str, Any]:
    """Queue worker handler for 'researcher' jobs."""
    inp = ResearcherInput.model_validate(payload)
    output = await run_researcher(inp.scholarship_id, session)
    return output.model_dump(mode="json")
