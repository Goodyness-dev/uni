"""Read-only official portal inspection and an explicit applicant handoff."""
from urllib.parse import urlsplit
from typing import Any
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.public_fetch import fetch_public_text
from app.core.tracing import trace_block, recovery_decision
from app.core.logging import logger
from app.db.models import Application, Scholarship, ApplicationEvent
from app.jobs.state_machine import transition_application
from app.services.public_pages import parse_page

PORTAL_HOSTS = {"apply.postgraduate.study.cam.ac.uk", "portal.csccentralonline.org.uk"}


async def inspect_portal(url: str) -> dict[str, Any]:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in PORTAL_HOSTS or parsed.username or parsed.password:
        return {"url": url, "blocker": "unconfigured_adapter", "read_only": True}
    with trace_block("official_portal_inspection", "TOOL", source_url=url, read_only=True):
        try:
            html = await fetch_public_text(url, allowed_hosts=PORTAL_HOSTS, max_redirects=2)
            page = parse_page(html, url)
            return {"url": url, "blocker": page["blocker"] or "applicant_completion",
                "sha256": page["sha256"], "retrieved_at": page["retrieved_at"], "read_only": True}
        except (httpx.HTTPError, ValueError, OSError, TimeoutError):
            logger.warning("Official portal inspection unavailable; handing off without a submission.")
            return {"url": url, "blocker": "portal_unavailable", "read_only": True}


async def handoff_real_portal(application: Application, scholarship: Scholarship,
    session: AsyncSession) -> dict[str, Any]:
    rules = scholarship.eligibility_rules or {}
    portal = rules.get("portal_url", scholarship.application_url)
    observation = await inspect_portal(portal)
    instructions = ("Open the official portal yourself, use your own genuine documents, and follow its login and verification steps. "
        "The fictional Tobi fixture is for testing and must not be submitted here. Download the prepared source notes for reference. "
        "ScholarPilot has not submitted this application and cannot verify an external receipt through this adapter.")
    with recovery_decision("real_portal_requires_applicant", ["human_handoff"]) as recovery:
        recovery.decide("human_handoff", "Respect portal verification and applicant-only submission rules.")
        recovery.finish("needs_human")
    logger.info("Real portal preparation completed; applicant handoff required.")
    session.add(ApplicationEvent(application_id=application.id, actor="coordinator", event_type="recovery_decision",
        payload={"action": "human_handoff", "reason": "Official portal requires the applicant.", "portal_url": portal}))
    await transition_application(application, "needs_human", "coordinator", {**observation,
        "portal_url": portal, "blocker_type": observation["blocker"], "instructions": instructions,
        "message": "Real university/portal preparation ready; applicant completion required."}, session)
    return {"application_id": str(application.id), "status": application.status, "external_submission": False}
