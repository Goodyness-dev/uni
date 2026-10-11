"""Tailor agent: drafts grounded scholarship CV summaries, bullets, and essays."""
from typing import Any

from app import db
from app.errors import LLMError, RunContext
from app.llm import call_llm
from app.models import (
    Dossier,
    Edge,
    Fact,
    Listing,
    Preferences,
    Segment,
    TailoredOutput,
)
from app.prompts import TAILOR_REVISE_SYSTEM, TAILOR_SYSTEM
from app.schemas import ReviseOut, TailorOut
from app.sensitive import strip_sensitive
from app.tracing import agent_span

CORE_CV_CATEGORIES = {"education", "grades", "work", "projects"}


def build_sources(
    listing: Listing,
    facts: list[Fact],
    dossier: Dossier,
    edges: list[Edge],
    prefs: Preferences,
) -> dict[str, str]:
    """Builds the closed dictionary of allowed grounding facts (ID -> text)."""
    allowed_facts = strip_sensitive(facts, listing, prefs.sensitive_consent)
    profile_map = {f.id: f for f in allowed_facts}
    dossier_map = {f.id: f for f in dossier.facts}

    selected_edges = [e for e in edges if e.selected]
    edge_profile_ids = {pid for e in selected_edges for pid in e.profile_fact_ids}
    edge_dossier_ids = {did for e in selected_edges for did in e.dossier_fact_ids}

    sources: dict[str, str] = {}

    for f in allowed_facts:
        if f.id in edge_profile_ids or f.category in CORE_CV_CATEGORIES:
            sources[f.id] = f.text

    for did in edge_dossier_ids:
        if did in dossier_map:
            sources[did] = dossier_map[did].text

    return sources


def _build_tailor_user_prompt(
    listing: Listing,
    sources: dict[str, str],
    edges: list[Edge],
) -> str:
    """Builds user prompt for tailor_v1."""
    selected_edges = [e for e in edges if e.selected]
    edge_lines = [f"- E{idx}: {e.reason} (use in {e.use_in})" for idx, e in enumerate(selected_edges, start=1)]
    source_lines = [f"{sid}: {text}" for sid, text in sources.items()]

    return (
        f"Scholarship: {listing.name}\n"
        f"Essay Prompt: {listing.essay_prompt}\n"
        f"Word Limit: {listing.essay_word_limit} words\n\n"
        f"Selected Edges:\n" + "\n".join(edge_lines) + "\n\n"
        f"Grounding Sources:\n" + "\n".join(source_lines)
    )


def _validate_segments(
    raw_segments: list[Any],
    sources: dict[str, str],
    section_name: str,
    ctx: RunContext,
) -> list[Segment]:
    """Filters out segments lacking citations or referencing unknown sources."""
    valid: list[Segment] = []
    for item in raw_segments:
        s_ids = [sid.strip() for sid in item.source_ids if sid.strip()]
        if not s_ids or any(sid not in sources for sid in s_ids):
            if ctx.run_id:
                db.add_event(
                    ctx.run_id,
                    ctx.application_id or None,
                    "tailor",
                    "segment_dropped",
                    f"Dropped {section_name} segment with ungrounded sources: {s_ids}",
                    {"section": section_name, "source_ids": s_ids},
                )
            continue
        valid.append(Segment(text=item.text.strip(), source_ids=s_ids, status="supported"))
    return valid


def _enforce_word_limit(
    essay: list[Segment],
    word_limit: int,
    listing: Listing,
    sources: dict[str, str],
    ctx: RunContext,
) -> list[Segment]:
    """Ensures essay segments adhere to word limits via revision and truncation."""
    word_count = sum(len(s.text.split()) for s in essay)
    if word_count <= word_limit:
        return essay

    # Truncate whole segments from the end if over limit
    truncated = list(essay)
    while truncated and sum(len(s.text.split()) for s in truncated) > word_limit:
        removed = truncated.pop()
        if ctx.run_id:
            db.add_event(
                ctx.run_id,
                ctx.application_id or None,
                "tailor",
                "segment_truncated",
                f"Removed essay segment to adhere to {word_limit} word limit: '{removed.text[:30]}...'",
            )
    return truncated


@agent_span("tailor", role="tailor", goal="draft grounded scholarship application materials")
def tailor_full(
    listing: Listing,
    sources: dict[str, str],
    edges: list[Edge],
    prefs: Preferences,
    ctx: RunContext | None = None,
) -> TailoredOutput:
    """Generates fully grounded CV summary, bullets, and essay."""
    ctx = ctx or RunContext()
    user_text = _build_tailor_user_prompt(listing, sources, edges)

    res = call_llm("tailor_v1", TAILOR_SYSTEM, user_text, TailorOut, ctx, temperature=0.5, max_tokens=2500)
    parsed = res.parsed
    if isinstance(parsed, dict):
        out = TailorOut.model_validate(parsed)
    elif isinstance(parsed, TailorOut):
        out = parsed
    else:
        out = TailorOut()

    summary = _validate_segments(out.cv_summary, sources, "cv_summary", ctx)
    bullets = _validate_segments(out.cv_bullets, sources, "cv_bullets", ctx)
    essay = _validate_segments(out.essay, sources, "essay", ctx)

    if not essay:
        raise LLMError("Empty essay after validation")

    final_essay = _enforce_word_limit(essay, listing.essay_word_limit, listing, sources, ctx)

    return TailoredOutput(
        cv_summary=summary,
        cv_bullets=bullets,
        essay=final_essay,
        mode="full",
        outline=[],
    )


def tailor_revise(
    listing: Listing,
    sources: dict[str, str],
    tailored: TailoredOutput,
    problem_segments: list[dict[str, Any]],
    ctx: RunContext | None = None,
) -> TailoredOutput:
    """Revises specific problem segments by index, keeping other segments unchanged."""
    ctx = ctx or RunContext()
    source_lines = [f"{sid}: {text}" for sid, text in sources.items()]
    prob_lines = [
        f"- Section: {p['section']}, Index: {p['segment_index']}, Issue: {p.get('reason', 'unsupported')}"
        for p in problem_segments
    ]
    user_text = (
        f"Scholarship: {listing.name}\n\n"
        f"Grounding Sources:\n" + "\n".join(source_lines) + "\n\n"
        f"Sentences to Revise:\n" + "\n".join(prob_lines)
    )

    res = call_llm("tailor_revise_v1", TAILOR_REVISE_SYSTEM, user_text, ReviseOut, ctx)
    parsed = res.parsed
    if isinstance(parsed, dict):
        rev_out = ReviseOut.model_validate(parsed)
    elif isinstance(parsed, ReviseOut):
        rev_out = parsed
    else:
        rev_out = ReviseOut()

    new_summary = list(tailored.cv_summary)
    new_bullets = list(tailored.cv_bullets)
    new_essay = list(tailored.essay)

    for rev in rev_out.revisions:
        s_ids = [sid.strip() for sid in rev.source_ids if sid.strip() and sid.strip() in sources]
        if not s_ids or not rev.text.strip():
            continue
        seg = Segment(text=rev.text.strip(), source_ids=s_ids, status="supported")
        if rev.section == "cv_summary" and 0 <= rev.segment_index < len(new_summary):
            new_summary[rev.segment_index] = seg
        elif rev.section == "cv_bullets" and 0 <= rev.segment_index < len(new_bullets):
            new_bullets[rev.segment_index] = seg
        elif rev.section == "essay" and 0 <= rev.segment_index < len(new_essay):
            new_essay[rev.segment_index] = seg

    return TailoredOutput(
        cv_summary=new_summary,
        cv_bullets=new_bullets,
        essay=new_essay,
        mode=tailored.mode,
        outline=tailored.outline,
    )
