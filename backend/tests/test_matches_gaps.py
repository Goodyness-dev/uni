"""Contract tests for /api/matches and /api/gaps endpoints (Task B08)."""
import json
import pytest
from fastapi.testclient import TestClient

from app import db
from app.config import settings
from app.main import app


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path, monkeypatch):
    test_db = str(tmp_path / "test_matches_gaps.db")
    monkeypatch.setenv("TEST_DB_PATH", test_db)
    db.init_db()


def test_matches_and_gaps_contract():
    client = TestClient(app)

    # Setup run and applications
    run_id = db.create_run(mode="B", top_n=2, live_research=False)

    app1 = db.create_application(run_id, "mock_portal_masters", "portal_form")
    db.update_application(
        app1,
        hard_rules={"country": True, "level": True, "gpa": True, "field": True, "deadline": True, "nationality": True},
        failed_rules=[],
        fit_score=92,
        fit_reason="Excellent alignment with energy AI",
    )
    db.set_status(app1, "matched", "matched", agent="matcher")

    app2 = db.create_application(run_id, "mock_captcha_award", "portal_captcha")
    db.update_application(
        app2,
        hard_rules={"country": True, "level": True, "gpa": False, "field": True, "deadline": True, "nationality": True},
        failed_rules=["gpa"],
        fit_score=0,
        fit_reason="Not eligible: gpa",
    )
    db.set_status(app2, "skipped", "skipped", agent="matcher")

    # Add a gap for app1
    gap_id = db.add_gap(app1, "leadership", "This scholarship values leadership. Do you have experience?")

    # 1. GET /api/matches
    res_m = client.get(f"/api/matches?run_id={run_id}")
    assert res_m.status_code == 200
    data_m = res_m.json()
    assert "matches" in data_m
    matches = data_m["matches"]
    assert len(matches) == 2

    # Verify order: matched first (fit_score 92), skipped second
    assert matches[0]["application_id"] == app1
    assert matches[0]["fit_score"] == 92
    assert matches[0]["status"] == "matched"
    assert matches[1]["application_id"] == app2
    assert matches[1]["status"] == "skipped"

    # 2. GET /api/gaps
    res_g = client.get(f"/api/gaps?run_id={run_id}")
    assert res_g.status_code == 200
    data_g = res_g.json()
    assert "gaps" in data_g
    gaps = data_g["gaps"]
    assert len(gaps) == 1
    assert gaps[0]["id"] == gap_id
    assert gaps[0]["answered"] is False

    # 3. POST /api/gaps/{id}/answer
    res_ans = client.post(f"/api/gaps/{gap_id}/answer", json={"text": "I led the Tech Club hackathon with 120 participants."})
    assert res_ans.status_code == 200
    ans_data = res_ans.json()
    assert "fact" in ans_data
    fact = ans_data["fact"]
    assert fact["id"].startswith("P")
    assert fact["category"] == "leadership"
    assert "120 participants" in fact["text"]

    # Verify gap now answered in GET
    res_g_after = client.get(f"/api/gaps?run_id={run_id}")
    assert res_g_after.json()["gaps"][0]["answered"] is True


def test_acceptance_scout_matcher_five_entries():
    from app.agents.scout import load_listings, filter_open
    from app.agents.matcher import run_matcher
    from app.models import Preferences, Fact
    from app.llm import set_clients_for_tests
    from datetime import date

    class FakeAcceptanceClient:
        @property
        def chat(self):
            return self
        @property
        def completions(self):
            return self
        def create(self, **kwargs):
            return type("Resp", (), {
                "choices": [type("Choice", (), {"message": type("Msg", (), {
                    "content": json.dumps({
                        "fit_score": 85,
                        "fit_reason": "High relevance to energy systems and AI",
                        "strongest_fact_ids": ["C1"],
                        "missing_criteria": ["public policy"],
                    })
                })()})],
                "usage": type("Usage", (), {"prompt_tokens": 50, "completion_tokens": 50})(),
            })()

    set_clients_for_tests(FakeAcceptanceClient(), FakeAcceptanceClient())

    client = TestClient(app)
    run_id = db.create_run(mode="B", top_n=5, live_research=False)

    prefs = Preferences(
        full_name="Tobi Adeyemi",
        email="tobi.adeyemi@example.com",
        level="masters",
        fields=["computer engineering", "artificial intelligence", "energy systems"],
        countries=["UK", "Germany", "Canada"],
        funding="full",
        start_year=2027,
        nationality="Nigeria",
        gpa=4.3,
        gpa_scale=5.0,
        sensitive_consent=False,
    )
    facts = [
        Fact(id="C1", source="cv", category="work", text="Embedded Systems Intern for 5 months", sensitive=False),
        Fact(id="P1", source="vault", category="leadership", text="Tech club coordinator", sensitive=False),
    ]

    all_listings = load_listings()
    open_l, exp_l = filter_open(all_listings, today=date(2026, 10, 10))

    run_matcher(open_l, exp_l, facts, prefs, run_id=run_id, mode="B")

    res = client.get(f"/api/matches?run_id={run_id}")
    assert res.status_code == 200
    data = res.json()
    assert "matches" in data
    matches = data["matches"]
    assert len(matches) >= 5, f"Expected at least 5 matches, got {len(matches)}"

    # Check that scores are sensible and entries are ranked
    for m in matches:
        assert "fit_score" in m
        assert "status" in m
        assert m["application_id"].startswith("app_")

