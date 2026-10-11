"""Edge Finder agent: identifies and ranks strongest applicant-scholarship alignments."""
from typing import Any

from app import db
from app.errors import RunContext
from app.llm import call_llm
from app.models import Dossier, Edge, Fact, Listing, Preferences
from app.prompts import EDGE_SYSTEM
from app.schemas import EdgeOut
from app.sensitive import strip_sensitive
from app.tracing import agent_span, tool_span


@tool_span("strip_sensitive", description="strip sensitive facts before edge finding")
def _strip_facts_for_edges(
    facts: list[Fact], listing: Listing, consent: bool
) -> list[Fact]:
    """Wraps strip_sensitive inside a TOOL span."""
    return strip_sensitive(facts, listing, consent)


def _build_edge_prompt(
    listing: Listing, dossier: Dossier, allowed_facts: list[Fact]
) -> str:
    """Builds prompt user text containing only allowed profile facts and dossier facts."""
    dossier_lines = [f"{df.id}: {df.text}" for df in dossier.facts]
    profile_lines = [f"{pf.id}: {pf.text}" for pf in allowed_facts]

    return (
        f"Scholarship: {listing.name}\n"
        f"Criteria: {listing.criteria_text}\n"
        f"Essay Prompt: {listing.essay_prompt}\n\n"
        f"Institutional Dossier Facts:\n" + "\n".join(dossier_lines) + "\n\n"
        f"Applicant Facts:\n" + "\n".join(profile_lines)
    )


def _validate_raw_edges(
    raw_edges: list[Any],
    allowed_ids: set[str],
    dossier_ids: set[str],
    ctx: RunContext,
) -> list[Any]:
    """Filters out hallucinated or invalid fact references."""
    valid = []
    for item in raw_edges:
        p_ids = [pid.strip() for pid in item.profile_fact_ids if pid.strip()]
        d_ids = [did.strip() for did in item.dossier_fact_ids if did.strip()]

        if not p_ids or not d_ids:
            continue

        invalid_p = [pid for pid in p_ids if pid not in allowed_ids]
        invalid_d = [did for did in d_ids if did not in dossier_ids]

        if invalid_p or invalid_d:
            reason = f"Invalid fact IDs referenced: {invalid_p + invalid_d}"
            if ctx.run_id:
                db.add_event(
                    ctx.run_id,
                    ctx.application_id or None,
                    "edge_finder",
                    "edge_dropped",
                    reason,
                    {"invalid_ids": invalid_p + invalid_d},
                )
            continue

        valid.append(item)
    return valid


def _normalize_use_in(raw_use: str) -> str:
    """Normalizes use_in to supported literal values: cv_bullet, essay_opening, essay_body, attachment."""
    low = raw_use.lower()
    if "bullet" in low:
        return "cv_bullet"
    if "opening" in low:
        return "essay_opening"
    if "attach" in low:
        return "attachment"
    return "essay_body"


@agent_span("edge_finder", role="edge_finder", goal="identifying competitive applicant-scholarship alignments")
def find_edges(
    listing: Listing,
    dossier: Dossier,
    facts: list[Fact],
    prefs: Preferences,
    ctx: RunContext | None = None,
) -> tuple[list[Edge], list[dict[str, Any]]]:
    """Finds, validates, ranks, and selects edges for an application."""
    ctx = ctx or RunContext()
    allowed = _strip_facts_for_edges(facts, listing, prefs.sensitive_consent)
    user_text = _build_edge_prompt(listing, dossier, allowed)

    res = call_llm("edge_v1", EDGE_SYSTEM, user_text, EdgeOut, ctx)
    parsed = res.parsed
    if isinstance(parsed, dict):
        out = EdgeOut.model_validate(parsed)
    elif isinstance(parsed, EdgeOut):
        out = parsed
    else:
        out = EdgeOut()

    allowed_ids = {f.id for f in allowed}
    dossier_ids = {f.id for f in dossier.facts}

    valid_items = _validate_raw_edges(out.edges, allowed_ids, dossier_ids, ctx)
    valid_items.sort(key=lambda x: float(x.strength), reverse=True)

    edges: list[Edge] = []
    selected_count = 0

    for idx, item in enumerate(valid_items, start=1):
        use_in = _normalize_use_in(item.use_in)
        strength = float(item.strength)
        is_selected = False

        if strength >= 0.6 and selected_count < 3:
            # Degraded dossier rule: only cv_bullet allowed if dossier is degraded
            if not dossier.degraded or use_in == "cv_bullet":
                is_selected = True
                selected_count += 1
                if ctx.run_id:
                    db.add_event(
                        ctx.run_id,
                        ctx.application_id or None,
                        "edge_finder",
                        "edge_selected",
                        f"Selected edge E{idx}: {item.reason}",
                        {"edge_id": f"E{idx}", "strength": strength},
                    )

        edge = Edge(
            id=f"E{idx}",
            profile_fact_ids=item.profile_fact_ids,
            dossier_fact_ids=item.dossier_fact_ids,
            reason=item.reason.strip(),
            use_in=use_in,  # type: ignore[arg-type]
            strength=strength,
            selected=is_selected,
        )
        edges.append(edge)

    gaps = [
        {"criterion": g.criterion.strip(), "question": g.question.strip()}
        for g in out.gaps[:2]
        if g.criterion.strip()
    ]

    return edges, gaps
