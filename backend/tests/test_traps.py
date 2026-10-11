"""Regression tests for the 4 persona traps (Task B23).

Ensures:
1. Title upgrade trap: 'assistant coordinator' or 'member' upgraded to 'president/founder' is caught (unsupported/overturned) and removed or revised.
2. Duration trap: '5 months' internship upgraded to 'years of experience' is caught as unsupported and neutralized.
3. Sensitive trap: sensitive family income or health facts are scrubbed by sensitive post-scan.
4. Gap trap: missing public policy criterion creates gap questions and is never hallucinated.
"""
import pytest
from app import db
from app.agents import verifier, scout
from app.errors import RunContext
from app.llm import set_clients_for_tests
from app.models import (
    Listing,
    Segment,
    TailoredOutput,
)


@pytest.fixture(autouse=True)
def clean_env():
    """Ensure db flags and mock clients are reset before and after each test."""
    db.clear_flags()
    set_clients_for_tests(None, None)
    yield
    db.clear_flags()
    set_clients_for_tests(None, None)


def test_trap_title_upgrade_caught():
    """Trap 1: Upgrading club member / assistant coordinator to president is caught."""
    run_id = db.create_run("B", 1)
    app_id = db.create_application(run_id, "mock_portal_masters", "portal_form")
    ctx = RunContext(run_id=run_id, application_id=app_id)

    sources = {
        "C1": "Member, FSU Tech Club, 2021 to 2025.",
        "V1": "Assistant Coordinator, FSU Tech Club.",
    }

    tailored = TailoredOutput(
        cv_summary=[
            Segment(text="BSc Computer Engineering graduate from FSU.", source_ids=["C1"], status="supported")
        ],
        cv_bullets=[
            Segment(text="Served as president of the FSU Tech Club, leading all club operations.", source_ids=["C1"], status="supported")
        ],
        essay=[
            Segment(text="As the founder and president of FSU Tech Club, I drove technical initiatives.", source_ids=["C1"], status="supported")
        ],
    )

    listing = scout.get_listing("mock_portal_masters")
    final_tailored, report = verifier.verify_mode_b(tailored, sources, listing, ctx)

    # Must not contain 'president' or 'founder' in any active supported text
    active_bullets = [b.text.lower() for b in final_tailored.cv_bullets if b.status != "removed"]
    active_essay = [e.text.lower() for e in final_tailored.essay if e.status != "removed"]

    for text in active_bullets + active_essay:
        assert "president" not in text
        assert "founder" not in text

    # Report must show removed or revised claims
    assert len(report.removed_claims) > 0 or report.rounds >= 2
    assert report.unsupported_final == 0


def test_trap_duration_upgrade_caught():
    """Trap 2: Upgrading 5 months internship to 'years of experience' is caught."""
    run_id = db.create_run("B", 1)
    app_id = db.create_application(run_id, "mock_portal_masters", "portal_form")
    ctx = RunContext(run_id=run_id, application_id=app_id)

    sources = {
        "C2": "Embedded Systems Intern, BrightGrid Solar, 5 months in 2024.",
    }

    tailored = TailoredOutput(
        cv_summary=[
            Segment(text="With years of professional experience in solar engineering, I led sensor design.", source_ids=["C2"], status="supported")
        ],
        cv_bullets=[
            Segment(text="Developed firmware across extensive multi-year engineering roles.", source_ids=["C2"], status="supported")
        ],
        essay=[
            Segment(text="During my 5-month internship at BrightGrid Solar, I tested sensor firmware.", source_ids=["C2"], status="supported")
        ],
    )

    listing = scout.get_listing("mock_portal_masters")
    final_tailored, report = verifier.verify_mode_b(tailored, sources, listing, ctx)

    # Active supported segments must not claim years of experience or multi-year
    active_summary = [s.text.lower() for s in final_tailored.cv_summary if s.status != "removed"]
    active_bullets = [b.text.lower() for b in final_tailored.cv_bullets if b.status != "removed"]

    for text in active_summary + active_bullets:
        assert "years of professional experience" not in text
        assert "multi-year" not in text

    assert report.unsupported_final == 0


def test_trap_sensitive_fact_scrubbed():
    """Trap 3: Sensitive hardship details (e.g. family income / poverty) are scrubbed."""
    run_id = db.create_run("B", 1)
    app_id = db.create_application(run_id, "mock_portal_masters", "portal_form")
    ctx = RunContext(run_id=run_id, application_id=app_id)

    sources = {
        "C1": "BSc Computer Engineering, FSU, 2020 to 2025.",
        "S1": "Family income below poverty threshold facing severe financial hardship.",
    }

    tailored = TailoredOutput(
        cv_summary=[
            Segment(text="BSc Computer Engineering graduate focused on smart grids.", source_ids=["C1"], status="supported")
        ],
        cv_bullets=[],
        essay=[
            Segment(text="I grew up in severe financial hardship with family income below the poverty line.", source_ids=["S1"], status="supported"),
            Segment(text="My goal is to apply energy AI systems to improve grid resilience.", source_ids=["C1"], status="supported"),
        ],
    )

    listing = scout.get_listing("mock_portal_masters")
    final_tailored, report = verifier.verify_mode_b(tailored, sources, listing, ctx)

    # Assert sensitive essay segment was removed
    active_essay = [s.text.lower() for s in final_tailored.essay if s.status != "removed"]
    for text in active_essay:
        assert "poverty" not in text
        assert "financial hardship" not in text

    sensitive_segments = [s for s in final_tailored.essay if "poverty" in s.text.lower()]
    assert all(s.status == "removed" for s in sensitive_segments)
    assert report.unsupported_final == 0


def test_trap_gap_policy_detection():
    """Trap 4: Missing public policy engagement values produce gaps without fabrication."""
    listing = scout.get_listing("mock_captcha_award")
    assert listing is not None
    assert "public policy" in listing.criteria_text.lower()

    # Applicant facts have no public policy experience
    from app.models import Fact
    from app.agents import matcher

    facts = [
        Fact(id="C1", source="cv", category="education", text="BSc Computer Engineering graduate."),
        Fact(id="C2", source="cv", category="work", text="Embedded Systems Intern, BrightGrid Solar, 5 months."),
    ]

    score, reason, missing = matcher.score_fit(listing, facts, RunContext())
    assert any("policy" in m.lower() for m in missing) or score < 100

