"""Researcher agent: gathers verified institutional facts and priorities."""
import json
import re
from pathlib import Path
from typing import Any

import httpx

from app import db
from app.config import settings
from app.errors import ResearchError, RunContext
from app.llm import call_llm
from app.models import Dossier, DossierFact, Listing
from app.prompts import RESEARCHER_SYSTEM
from app.schemas import ResearcherOut
from app.tracing import agent_span, recovery_decision, set_attrs, tool_span

INJECTION_REGEX = re.compile(
    r"ignore previous|ignore all|disregard|system prompt|you are now|do not tell",
    re.IGNORECASE,
)


def get_cache_path(listing_id: str) -> Path | None:
    """Finds path to cached dossier if available."""
    candidates = [
        Path(f"data/dossier_cache/{listing_id}.json"),
        Path(f"backend/data/dossier_cache/{listing_id}.json"),
        Path(__file__).resolve().parent.parent.parent / "data" / "dossier_cache" / f"{listing_id}.json",
    ]
    for p in candidates:
        if p.is_file():
            return p
    return None


@tool_span("fetch_page", description="fetch and strip HTML page text")
def strip_html(html_text: str) -> str:
    """Strips HTML tags, styles, and scripts from page text."""
    text = re.sub(r"<script\b[^>]*>.*?</script>", "", html_text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<style\b[^>]*>.*?</style>", "", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _sanitize_injection(raw_html: str, ctx: RunContext) -> str:
    """Splits into lines, removes adversarial prompts, and wraps in delimiters."""
    lines = raw_html.splitlines()
    dropped = 0
    clean_lines: list[str] = []

    for line in lines:
        if INJECTION_REGEX.search(line):
            dropped += 1
        else:
            clean_lines.append(line)

    if dropped > 0 and ctx.run_id:
        db.add_event(
            ctx.run_id,
            ctx.application_id or None,
            "researcher",
            "injection_detected",
            f"Dropped {dropped} adversarial prompt injection lines",
            {"dropped_count": dropped},
        )

    clean_text = strip_html("\n".join(clean_lines))
    return clean_text


def _verify_and_build_facts(
    facts_raw: list[Any], page_text: str, source_url: str
) -> list[DossierFact]:
    """Ensures each extracted fact snippet exists exactly in the page text."""
    norm_page = re.sub(r"\s+", " ", page_text.lower())
    now = db.now_str()
    verified: list[DossierFact] = []
    idx = 1

    for item in facts_raw:
        snippet = item.snippet.strip()
        norm_snippet = re.sub(r"\s+", " ", snippet.lower())
        if not norm_snippet or norm_snippet not in norm_page:
            continue

        fact = DossierFact(
            id=f"D{idx}",
            topic=item.topic.strip(),
            text=item.text.strip(),
            source_url=source_url,
            snippet=snippet,
            retrieved_at=now,
        )
        verified.append(fact)
        idx += 1

    return verified


def fetch_live(listing: Listing, ctx: RunContext) -> list[DossierFact]:
    """Fetches institution page text live, defends injections, and extracts facts."""
    flags = db.get_flags().get("flags", {})
    if flags.get("research_down"):
        if ctx.run_id:
            db.add_event(
                ctx.run_id,
                ctx.application_id or None,
                agent="researcher",
                type_="failure_injected",
                message="Injected failure: research_down",
                data={"flag": "research_down"},
            )
        raise ResearchError("simulated")


    if listing.is_mock:
        url = f"{settings.public_base_url}/portal/about/{listing.id}"
        try:
            resp = httpx.get(url, timeout=10.0, follow_redirects=False)
            if resp.status_code != 200:
                raise ResearchError(f"HTTP {resp.status_code}")
            raw_html = resp.text
        except Exception as e:
            raise ResearchError(str(e)) from e
    elif settings.crustdata_api_key:
        raise ResearchError("not configured")
    else:
        raise ResearchError("no live research source configured")

    clean_text = _sanitize_injection(raw_html, ctx)
    wrapped = f"<<<PAGE_TEXT\n{clean_text}\nPAGE_TEXT>>>"

    res = call_llm("researcher_v1", RESEARCHER_SYSTEM, wrapped, ResearcherOut, ctx)
    parsed = res.parsed
    if isinstance(parsed, dict):
        out = ResearcherOut.model_validate(parsed)
    elif isinstance(parsed, ResearcherOut):
        out = parsed
    else:
        out = ResearcherOut()

    verified = _verify_and_build_facts(out.facts, clean_text, url)
    if not verified:
        raise ResearchError("no verified facts")

    return verified


def _load_cached_dossier(listing_id: str) -> Dossier | None:
    """Loads cached dossier from local JSON file."""
    cache_path = get_cache_path(listing_id)
    if not cache_path:
        return None
    try:
        raw = json.loads(cache_path.read_text(encoding="utf-8"))
        facts = [DossierFact.model_validate(f) for f in raw.get("facts", [])]
        return Dossier(listing_id=listing_id, facts=facts, degraded=False)
    except Exception:
        return None


def _make_degraded_dossier(listing: Listing) -> Dossier:
    """Builds a degraded dossier from the listing criteria text."""
    words = listing.criteria_text.split()
    text = " ".join(words[:40])
    snippet = " ".join(words[:25])
    fact = DossierFact(
        id="D1",
        topic="scholarship_priorities",
        text=text,
        source_url=listing.source_url,
        snippet=snippet,
        retrieved_at=db.now_str(),
    )
    return Dossier(listing_id=listing.id, facts=[fact], degraded=True)


@agent_span("researcher", role="researcher", goal="sourcing verifiable institutional priorities")
def build_dossier(
    listing: Listing, live: bool = False, ctx: RunContext | None = None
) -> Dossier:
    """Builds an institutional dossier via live scraping, cached JSON, or degraded fallback."""
    ctx = ctx or RunContext()
    flags = db.get_flags().get("flags", {})
    should_try_live = live or bool(flags.get("research_down"))

    if should_try_live:
        try:
            live_facts = fetch_live(listing, ctx)
            return Dossier(listing_id=listing.id, facts=live_facts, degraded=False)
        except ResearchError:
            with recovery_decision(
                trigger="research_unreachable",
                options=["use_cache", "degrade_dossier"],
            ) as rec:
                rec.decide(
                    chosen="use_cache",
                    reason="live source failed, a cached dossier with source URLs exists",
                )
                rec.finish("success")

            if ctx.run_id:
                db.add_event(
                    ctx.run_id,
                    ctx.application_id or None,
                    "researcher",
                    "recovery_decision",
                    "Recovery chosen: use_cache because live source failed, a cached dossier with source URLs exists",
                    {"trigger": "research_unreachable", "options": ["use_cache", "degrade_dossier"], "chosen": "use_cache"},
                )
                db.add_event(
                    ctx.run_id,
                    ctx.application_id or None,
                    "researcher",
                    "research_used_cache",
                    "Falling back to cached dossier",
                )


    cached = _load_cached_dossier(listing.id)
    if cached is not None:
        return cached

    return _make_degraded_dossier(listing)
