"""Matches API endpoint."""
import json
from typing import Any

from fastapi import APIRouter

from app import db
from app.agents.scout import load_listings
from app.models import HardRuleResults, Match

router = APIRouter(prefix="/api/matches", tags=["matches"])


@router.get("")
def get_matches(run_id: str | None = None) -> dict[str, Any]:
    """Returns matches for a given run (or latest run), ranked by fit score."""
    if not run_id:
        latest = db.latest_run()
        if not latest:
            return {"matches": []}
        run_id = latest["run_id"]

    applications = db.list_applications(run_id)
    if not applications:
        return {"matches": []}

    try:
        listings_map = {l.id: l for l in load_listings()}
    except Exception:
        listings_map = {}

    matches: list[Match] = []
    for app in applications:
        lid = app.get("listing_id", "")
        listing = listings_map.get(lid)

        hr_raw = (
            json.loads(app["hard_rules_json"])
            if app.get("hard_rules_json")
            else {}
        )
        if hr_raw:
            hr = HardRuleResults.model_validate(hr_raw)
        else:
            hr = HardRuleResults(
                country=True, level=True, gpa=True, field=True, deadline=True, nationality=True
            )

        failed_rules = (
            json.loads(app["failed_rules_json"])
            if app.get("failed_rules_json")
            else []
        )

        name = listing.name if listing else app.get("name", lid)
        country = listing.country if listing else "Unknown"
        level = listing.level if listing else "masters"
        deadline = listing.deadline if listing else ""
        is_mock = listing.is_mock if listing else False

        match = Match(
            application_id=app["id"],
            listing_id=lid,
            name=name,
            is_mock=is_mock,
            country=country,
            level=level,
            deadline=deadline,
            channel=app.get("channel", "package_only"),
            fit_score=int(app.get("fit_score") or 0),
            fit_reason=app.get("fit_reason") or "",
            status=app.get("status", "found"),
            hard_rule_results=hr,
            failed_rules=failed_rules,
        )
        matches.append(match)

    # Sort: non-skipped by fit_score descending; skipped at the end
    non_skipped = [m for m in matches if m.status != "skipped"]
    non_skipped.sort(key=lambda m: m.fit_score, reverse=True)

    skipped = [m for m in matches if m.status == "skipped"]

    ordered = non_skipped + skipped
    return {"matches": [m.model_dump() for m in ordered]}
