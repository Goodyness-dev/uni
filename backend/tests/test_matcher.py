"""Tests for Matcher agent, hard rules, and fit scoring (Task B08)."""
from datetime import date
import json
import pytest

from app import db
from app.agents.matcher import hard_rules, run_matcher, score_fit
from app.config import settings
from app.errors import RunContext
from app.llm import set_clients_for_tests
from app.models import Fact, Listing, Preferences


class DummyChoice:
    def __init__(self, content: str):
        self.message = type("DummyMsg", (), {"content": content})()


class DummyUsage:
    prompt_tokens = 60
    completion_tokens = 60


class DummyResp:
    def __init__(self, content: str):
        self.choices = [DummyChoice(content)]
        self.usage = DummyUsage()


class FakeMatcherClient:
    def __init__(self, score: int = 85, missing: list[str] | None = None):
        self.score = score
        self.missing = missing or ["public policy"]

    @property
    def chat(self):
        return self

    @property
    def completions(self):
        return self

    def create(self, **kwargs):
        content = json.dumps({
            "fit_score": self.score,
            "fit_reason": "Strong alignment with energy and AI projects.",
            "strongest_fact_ids": ["C1", "P1"],
            "missing_criteria": self.missing,
        })
        return DummyResp(content)


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path, monkeypatch):
    test_db = str(tmp_path / "test_matcher.db")
    monkeypatch.setenv("TEST_DB_PATH", test_db)
    db.init_db()


def make_test_listing(**overrides) -> Listing:
    defaults = {
        "id": "test_scholarship",
        "name": "Test Scholarship",
        "is_mock": True,
        "provider": "Test Institute",
        "country": "UK",
        "level": "masters",
        "fields": ["computer engineering", "artificial intelligence"],
        "min_gpa": 3.0,
        "gpa_scale": 4.0,
        "eligible_nationalities": ["Nigeria"],
        "deadline": "2026/12/01",
        "channel": "portal_form",
        "criteria_text": "Excellence in computer engineering and artificial intelligence.",
        "essay_prompt": "Describe your vision.",
    }
    defaults.update(overrides)
    return Listing.model_validate(defaults)


def test_hard_rules_gpa_normalization_by_hand():
    # Applicant: 4.30 / 5.00 = 0.86
    prefs = Preferences(
        gpa=4.3,
        gpa_scale=5.0,
        level="masters",
        countries=["UK"],
        fields=["computer engineering"],
        nationality="Nigeria",
    )

    # 1. Listing requiring 3.5 / 4.0 = 0.875 -> 0.86 < 0.875, FAILS!
    l_high = make_test_listing(min_gpa=3.5, gpa_scale=4.0)
    hr_high = hard_rules(l_high, prefs, today=date(2026, 10, 10))
    assert hr_high.gpa is False

    # 2. Listing requiring 3.0 / 4.0 = 0.75 -> 0.86 >= 0.75, PASSES!
    l_mid = make_test_listing(min_gpa=3.0, gpa_scale=4.0)
    hr_mid = hard_rules(l_mid, prefs, today=date(2026, 10, 10))
    assert hr_mid.gpa is True

    # 3. Listing requiring 0.0 -> PASSES!
    l_zero = make_test_listing(min_gpa=0.0)
    hr_zero = hard_rules(l_zero, prefs, today=date(2026, 10, 10))
    assert hr_zero.gpa is True


def test_hard_rules_deadline_boundary_today_passes():
    prefs = Preferences(gpa=4.3, gpa_scale=5.0, level="masters", countries=["UK"], nationality="Nigeria")
    listing = make_test_listing(deadline="2026/11/15")

    # Deadline is 2026/11/15: on 2026/11/15 it passes
    assert hard_rules(listing, prefs, today=date(2026, 11, 15)).deadline is True

    # On 2026/11/16 it fails
    assert hard_rules(listing, prefs, today=date(2026, 11, 16)).deadline is False


def test_hard_rules_nationality_and_field_containment():
    prefs = Preferences(
        gpa=4.3, gpa_scale=5.0, level="masters", nationality="Nigeria",
        fields=["artificial intelligence"], countries=[]
    )

    # Empty nationality list passes anyone
    l1 = make_test_listing(eligible_nationalities=[])
    assert hard_rules(l1, prefs, today=date(2026, 10, 10)).nationality is True

    # Mismatched nationality fails
    l2 = make_test_listing(eligible_nationalities=["Ghana", "Kenya"])
    assert hard_rules(l2, prefs, today=date(2026, 10, 10)).nationality is False

    # Field containment: "artificial intelligence" in listing's "artificial intelligence and robotics"
    l3 = make_test_listing(fields=["artificial intelligence and robotics"])
    assert hard_rules(l3, prefs, today=date(2026, 10, 10)).field is True


def test_score_fit_clamping_and_gaps():
    # Model returns 150 -> clamped to 100
    set_clients_for_tests(FakeMatcherClient(score=150, missing=["policy", "ethics", "finance"]), FakeMatcherClient())

    listing = make_test_listing()
    facts = [Fact(id="C1", source="cv", category="work", text="Embedded intern", sensitive=False)]
    score, reason, missing = score_fit(listing, facts, RunContext())

    assert score == 100
    assert len(missing) == 2  # Max 2
    assert missing == ["policy", "ethics"]


def test_run_matcher_creates_applications_and_gaps():
    set_clients_for_tests(FakeMatcherClient(score=88, missing=["public policy"]), FakeMatcherClient())

    # Create run in DB
    run_id = db.create_run(mode="B", top_n=2, live_research=False)

    prefs = Preferences(
        gpa=4.3, gpa_scale=5.0, level="masters", nationality="Nigeria",
        fields=["computer engineering"], countries=["UK"]
    )
    facts = [
        Fact(id="C1", source="cv", category="work", text="Embedded systems intern", sensitive=False),
        Fact(id="P1", source="vault", category="leadership", text="Tech club coordinator", sensitive=False),
    ]

    open_l = [
        make_test_listing(id="l_pass", min_gpa=3.0, gpa_scale=4.0),
        make_test_listing(id="l_fail", min_gpa=3.8, gpa_scale=4.0),  # 0.86 < 0.95 -> fails GPA
    ]
    expired_l = [
        make_test_listing(id="l_expired", deadline="2026/01/01"),
    ]

    app_ids = run_matcher(open_l, expired_l, facts, prefs, run_id=run_id, mode="B")
    assert len(app_ids) == 3

    # Check passed application
    app_pass = db.get_application(app_ids[0])
    assert app_pass["status"] == "matched"
    assert app_pass["fit_score"] == 88

    # Gaps created for matched application
    gaps = db.list_gaps(run_id)
    assert len(gaps) == 1
    assert gaps[0]["criterion"] == "public policy"

    # Check failed application
    app_fail = db.get_application(app_ids[1])
    assert app_fail["status"] == "skipped"
    assert "gpa" in app_fail["failed_rules_json"]

    # Check expired application
    app_exp = db.get_application(app_ids[2])
    assert app_exp["status"] == "skipped"
    assert "deadline" in app_exp["failed_rules_json"]
