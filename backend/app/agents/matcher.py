"""Matcher agent: computes eligibility hard rules and scores scholarship fit."""
from datetime import date, datetime
from typing import Any

from app import db
from app.errors import RunContext
from app.llm import call_llm
from app.models import Fact, HardRuleResults, Listing, Preferences
from app.prompts import MATCHER_SYSTEM
from app.schemas import MatcherOut
from app.sensitive import strip_sensitive
from app.tracing import agent_span, tool_span


@tool_span("hard_rules", description="evaluate eligibility hard rules")
def hard_rules(
    listing: Listing, prefs: Preferences, today: date | None = None
) -> HardRuleResults:
    """Evaluates strict eligibility hard rules against applicant preferences."""
    if today is None:
        today = db.today_date()

    # 1. Country: empty prefs passes, else listing country in prefs
    country_ok = (not prefs.countries) or any(
        listing.country.strip().lower() == c.strip().lower() for c in prefs.countries
    )

    # 2. Level: listing level equals applicant level
    level_ok = listing.level.strip().lower() == prefs.level.strip().lower()

    # 3. GPA: min_gpa == 0 passes, else normalized applicant >= normalized min
    if listing.min_gpa == 0.0:
        gpa_ok = True
    else:
        app_norm = (prefs.gpa / prefs.gpa_scale) if prefs.gpa_scale > 0 else 0.0
        req_norm = (listing.min_gpa / listing.gpa_scale) if listing.gpa_scale > 0 else 0.0
        gpa_ok = app_norm >= req_norm

    # 4. Field: empty prefs passes, else substring overlap in either direction
    if not prefs.fields:
        field_ok = True
    else:
        pref_fields = [f.strip().lower() for f in prefs.fields if f.strip()]
        list_fields = [f.strip().lower() for f in listing.fields if f.strip()]
        field_ok = any(
            (pf in lf) or (lf in pf)
            for pf in pref_fields
            for lf in list_fields
        )

    # 5. Deadline: deadline on or after today
    try:
        deadline_date = datetime.strptime(listing.deadline, "%Y/%m/%d").date()
        deadline_ok = deadline_date >= today
    except ValueError:
        deadline_ok = False

    # 6. Nationality: empty listing eligible list passes, else applicant in list
    if not listing.eligible_nationalities:
        nat_ok = True
    else:
        nat_ok = any(
            prefs.nationality.strip().lower() == n.strip().lower()
            for n in listing.eligible_nationalities
        )

    return HardRuleResults(
        country=country_ok,
        level=level_ok,
        gpa=gpa_ok,
        field=field_ok,
        deadline=deadline_ok,
        nationality=nat_ok,
    )


def score_fit(
    listing: Listing, facts: list[Fact], ctx: RunContext
) -> tuple[int, str, list[str]]:
    """Calls matcher_v1 prompt with stripped facts to compute fit score and gaps."""
    allowed = strip_sensitive(facts, listing, consent=False)
    facts_lines = [f"{f.id}: {f.text}" for f in allowed]
    facts_block = "\n".join(facts_lines)

    user_text = (
        f"Scholarship: {listing.name}\n"
        f"Criteria: {listing.criteria_text}\n"
        f"Essay Prompt: {listing.essay_prompt}\n\n"
        f"Applicant Facts:\n{facts_block}"
    )

    res = call_llm("matcher_v1", MATCHER_SYSTEM, user_text, MatcherOut, ctx)
    parsed = res.parsed
    if isinstance(parsed, dict):
        out = MatcherOut.model_validate(parsed)
    elif isinstance(parsed, MatcherOut):
        out = parsed
    else:
        out = MatcherOut(fit_score=50, fit_reason="Evaluated from profile facts.")

    clamped_score = max(0, min(100, int(out.fit_score)))
    fit_reason = out.fit_reason.strip() or "Good profile alignment."
    missing = [c.strip() for c in out.missing_criteria if c.strip()][:2]
    return clamped_score, fit_reason, missing


def _process_single_listing(
    listing: Listing,
    facts: list[Fact],
    prefs: Preferences,
    run_id: str,
    ctx: RunContext,
) -> str:
    """Evaluates rules and fit for an open listing, returning created app_id."""
    app_id = db.create_application(run_id, listing.id, listing.channel)
    hr = hard_rules(listing, prefs)

    failed: list[str] = []
    if not hr.country:
        failed.append("country")
    if not hr.level:
        failed.append("level")
    if not hr.gpa:
        failed.append("gpa")
    if not hr.field:
        failed.append("field")
    if not hr.deadline:
        failed.append("deadline")
    if not hr.nationality:
        failed.append("nationality")

    if failed:
        reason = f"Not eligible: {', '.join(failed)}"
        db.update_application(
            app_id,
            hard_rules=hr.model_dump(),
            failed_rules=failed,
            fit_score=0,
            fit_reason=reason,
        )
        db.set_status(app_id, "skipped", reason, agent="matcher")
        return app_id

    fit_score, fit_reason, missing = score_fit(listing, facts, ctx)
    db.update_application(
        app_id,
        hard_rules=hr.model_dump(),
        failed_rules=[],
        fit_score=fit_score,
        fit_reason=fit_reason,
    )
    db.set_status(app_id, "matched", fit_reason, agent="matcher")

    for crit in missing:
        q = f"This scholarship values {crit}. Do you have experience with it?"
        db.add_gap(app_id, crit, q)

    return app_id


def _process_expired_listing(listing: Listing, run_id: str) -> str:
    """Records an expired listing as skipped with deadline passed reason."""
    app_id = db.create_application(run_id, listing.id, listing.channel)
    hr = HardRuleResults(
        country=True, level=True, gpa=True, field=True, deadline=False, nationality=True
    )
    db.update_application(
        app_id,
        hard_rules=hr.model_dump(),
        failed_rules=["deadline"],
        fit_score=0,
        fit_reason="Deadline passed",
    )
    db.set_status(app_id, "skipped", "Deadline passed", agent="matcher")
    return app_id


@agent_span("matcher", role="matcher", goal="evaluate eligibility hard rules and score scholarship fit")
def run_matcher(
    listings: list[Listing],
    expired: list[Listing],
    facts: list[Fact],
    prefs: Preferences,
    run_id: str,
    mode: str = "B",
    ctx: RunContext | None = None,
) -> list[str]:
    """Runs Scout-filtered listings through hard rules and fit scoring."""
    ctx = ctx or RunContext(run_id=run_id)
    app_ids: list[str] = []

    for listing in listings:
        app_ids.append(_process_single_listing(listing, facts, prefs, run_id, ctx))

    for listing in expired:
        app_ids.append(_process_expired_listing(listing, run_id))

    try:
        from app import notify
        if hasattr(notify, "tpl_matches_found"):
            # If notify helpers exist
            pass
    except (ImportError, AttributeError):
        pass

    return app_ids
