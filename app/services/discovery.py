"""Bounded discovery and dated observations from the supplied official-source catalog."""
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.tracing import trace_block, set_attrs
from app.db.models import Scholarship, Job
from app.services.public_pages import crawl_sources


def source_config(scholarship: Scholarship) -> dict[str, Any]:
    entries = json.loads(Path("backend/data/research_sources.json").read_text(encoding="utf-8"))
    identifier = (scholarship.eligibility_rules or {}).get("catalog_id")
    return entries.get(identifier, {})


def deadline_observation(text: str, year_hint: int | None = None) -> dict[str, Any]:
    months = "January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec"
    pattern = r"(?:closing date|application deadline|funding deadline|applications close|deadline)[^.!?]{0,140}?((?:\d{1,2}\s+(?:" + months + r")|(?:" + months + r")\.?\s+\d{1,2}),?\s*(?:20\d{2})?)"
    candidates = []
    for match in re.finditer(pattern, text, re.I):
        raw = match.group(1).strip().replace(",", "").replace(".", "")
        if not re.search(r"20\d{2}", raw):
            if year_hint is None:
                continue
            raw += " " + str(year_hint)
        for fmt in ("%d %B %Y", "%d %b %Y", "%B %d %Y", "%b %d %Y"):
            try:
                stamp = datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
                time_match = re.search(r"\b(\d{1,2})[:.](\d{2})\s*(BST|GMT|UTC)\b", match.group(0), re.I)
                if time_match:
                    hour, minute, zone = time_match.groups()
                    stamp = stamp.replace(hour=int(hour), minute=int(minute))
                    if zone.upper() == "BST":
                        stamp -= timedelta(hours=1)
                candidates.append(stamp.isoformat())
                break
            except ValueError:
                continue
    dates = sorted(set(candidates))
    return {"deadline": dates[0] if len(dates) == 1 else None,
        "ambiguous": len(dates) > 1, "candidates": dates, "year_hint_used": year_hint is not None}


def observe_pages(pages: list[dict[str, Any]], year_hint: int | None = None) -> dict[str, Any]:
    text = " ".join(page.get("text", "") for page in pages if not page.get("blocker"))
    lower = text.lower()
    closed = any(term in lower for term in ("closed for applications", "applications are closed", "applications have closed"))
    opened = bool(re.search(r"applications.{0,110}(?:now open|are open)", lower))
    dates = deadline_observation(text, year_hint)
    deadline = datetime.fromisoformat(dates["deadline"]) if dates["deadline"] else None
    if deadline and deadline < datetime.now(timezone.utc):
        closed = True
    policy = "restricted" if "strictly prohibited" in lower and "artificial intelligence" in lower else "unknown"
    return {**dates, "state": "closed" if closed else "open" if opened or deadline else "unverified",
        "ai_policy": policy, "source_count": sum(bool(p.get("text")) for p in pages),
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "sources": [{"url": p["url"], "sha256": p.get("sha256"), "retrieved_at": p.get("retrieved_at"),
            "blocker": p.get("blocker")} for p in pages]}


async def refresh_catalog(session: AsyncSession, limit: int = 3) -> list[dict[str, Any]]:
    scholarships = (await session.execute(select(Scholarship).where(Scholarship.source == "listings.json")
        .order_by(Scholarship.last_verified_at.asc().nullsfirst(), Scholarship.created_at))).scalars().all()
    results = []
    for scholarship in scholarships:
        config = source_config(scholarship)
        if not config or len(results) >= limit:
            continue
        with trace_block("scholarship_discovery", "RETRIEVER", scholarship_id=str(scholarship.id)) as span:
            pages = await crawl_sources(config["urls"], set(config["allowed_hosts"]), session, force=True)
            observation = observe_pages(pages, config.get("deadline_year"))
            rules = {**scholarship.eligibility_rules, "_source_observation": observation,
                "ai_policy": observation["ai_policy"], "research_urls": config["urls"],
                "portal_url": config.get("portal_url", scholarship.application_url),
                "portal_policy": config.get("portal_policy", "human_handoff")}
            scholarship.eligibility_rules = rules
            scholarship.deadline = datetime.fromisoformat(observation["deadline"]) if observation["deadline"] else None
            scholarship.last_verified_at = datetime.now(timezone.utc) if observation["source_count"] else None
            scholarship.status = "active" if observation["state"] == "open" else observation["state"]
            leads = sorted({link for page in pages for link in page.get("links", [])
                if "scholarship" in link.lower() and any(link.startswith("https://" + host + "/") for host in config["allowed_hosts"])})[:12]
            session.add(Job(type="discovery_observation", status="completed", payload={
                "scholarship_id": str(scholarship.id), "observation": observation, "discovered_links": leads}))
            await session.commit()
            set_attrs(span, source_count=observation["source_count"], observed_state=observation["state"])
            results.append({"id": str(scholarship.id), "title": scholarship.title, **observation, "discovered_links": leads})
    return results
