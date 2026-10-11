"""Tests for Edge Finder agent, validation, threshold, and degraded rule (Task B10)."""
import json
import pytest

from app import db
from app.agents.edge_finder import find_edges, _build_edge_prompt
from app.config import settings
from app.errors import RunContext
from app.llm import set_clients_for_tests
from app.models import Dossier, DossierFact, Fact, Listing, Preferences


class DummyChoice:
    def __init__(self, content: str):
        self.message = type("DummyMsg", (), {"content": content})()


class DummyResp:
    def __init__(self, content: str):
        self.choices = [DummyChoice(content)]
        self.usage = type("Usage", (), {"prompt_tokens": 50, "completion_tokens": 50})()


class FakeEdgeClient:
    def __init__(self, edges=None, gaps=None):
        self.edges = edges or []
        self.gaps = gaps or []

    @property
    def chat(self):
        return self

    @property
    def completions(self):
        return self

    def create(self, **kwargs):
        content = json.dumps({"edges": self.edges, "gaps": self.gaps})
        return DummyResp(content)


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path, monkeypatch):
    test_db = str(tmp_path / "test_edge_finder.db")
    monkeypatch.setenv("TEST_DB_PATH", test_db)
    db.init_db()


def make_test_listing() -> Listing:
    return Listing.model_validate({
        "id": "mock_portal_masters",
        "name": "Aurora Energy AI Scholarship",
        "is_mock": True,
        "provider": "Aurora Technical University",
        "country": "UK",
        "level": "masters",
        "fields": ["computer engineering"],
        "deadline": "2026/12/01",
        "channel": "portal_form",
        "criteria_text": "Community impact, solar projects and leadership.",
        "essay_prompt": "Describe your impact.",
    })


def make_test_dossier(degraded=False) -> Dossier:
    return Dossier(
        listing_id="mock_portal_masters",
        degraded=degraded,
        facts=[
            DossierFact(id="D1", topic="program_focus", text="Energy AI programme", source_url="", snippet="Energy AI", retrieved_at="2026/10/10"),
            DossierFact(id="D2", topic="values", text="Values community impact", source_url="", snippet="community impact", retrieved_at="2026/10/10"),
        ]
    )


def test_invalid_fact_ids_dropped():
    # Model hallucinates P99 (not in profile) and D99 (not in dossier)
    fake_edges = [
        {"profile_fact_ids": ["P99"], "dossier_fact_ids": ["D1"], "reason": "Hallucinated profile", "use_in": "essay", "strength": 0.9},
        {"profile_fact_ids": ["C1"], "dossier_fact_ids": ["D99"], "reason": "Hallucinated dossier", "use_in": "essay", "strength": 0.9},
        {"profile_fact_ids": ["C1"], "dossier_fact_ids": ["D1"], "reason": "Valid edge", "use_in": "essay", "strength": 0.8},
    ]
    set_clients_for_tests(FakeEdgeClient(fake_edges), FakeEdgeClient(fake_edges))

    listing = make_test_listing()
    dossier = make_test_dossier()
    facts = [Fact(id="C1", source="cv", category="work", text="Embedded solar intern", sensitive=False)]
    prefs = Preferences()

    edges, gaps = find_edges(listing, dossier, facts, prefs, RunContext(run_id="run_1"))
    assert len(edges) == 1
    assert edges[0].id == "E1"
    assert edges[0].reason == "Valid edge"


def test_strength_threshold_and_max_three_selected():
    fake_edges = [
        {"profile_fact_ids": ["C1"], "dossier_fact_ids": ["D1"], "reason": "Edge 1", "use_in": "essay", "strength": 0.95},
        {"profile_fact_ids": ["C1"], "dossier_fact_ids": ["D2"], "reason": "Edge 2", "use_in": "essay", "strength": 0.85},
        {"profile_fact_ids": ["C1"], "dossier_fact_ids": ["D1"], "reason": "Edge 3", "use_in": "cv_bullet", "strength": 0.75},
        {"profile_fact_ids": ["C1"], "dossier_fact_ids": ["D2"], "reason": "Edge 4", "use_in": "cv_bullet", "strength": 0.65},
        {"profile_fact_ids": ["C1"], "dossier_fact_ids": ["D1"], "reason": "Edge 5", "use_in": "essay", "strength": 0.45},
    ]
    set_clients_for_tests(FakeEdgeClient(fake_edges), FakeEdgeClient(fake_edges))

    listing = make_test_listing()
    dossier = make_test_dossier()
    facts = [Fact(id="C1", source="cv", category="work", text="Intern", sensitive=False)]
    prefs = Preferences()

    edges, gaps = find_edges(listing, dossier, facts, prefs, RunContext(run_id="run_1"))
    assert len(edges) == 5

    # Top 3 are selected (strength 0.95, 0.85, 0.75)
    selected = [e for e in edges if e.selected]
    assert len(selected) == 3
    assert [e.id for e in selected] == ["E1", "E2", "E3"]
    # 4th (0.65) was capped by max 3; 5th (0.45) is below 0.6 threshold
    assert edges[3].selected is False
    assert edges[4].selected is False


def test_sensitive_fact_absent_from_prompt_text():
    listing = make_test_listing()
    dossier = make_test_dossier()
    facts = [
        Fact(id="C1", source="cv", category="work", text="Embedded solar intern", sensitive=False),
        Fact(id="P1", source="vault", category="hardships", text="Family income hardship in 2nd year", sensitive=True),
    ]
    prefs = Preferences(sensitive_consent=False)

    from app.sensitive import strip_sensitive
    allowed = strip_sensitive(facts, listing, prefs.sensitive_consent)
    prompt_text = _build_edge_prompt(listing, dossier, allowed)

    assert "Embedded solar intern" in prompt_text
    assert "Family income hardship" not in prompt_text
    assert "P1" not in prompt_text


def test_degraded_dossier_rule():
    # When dossier is degraded, only cv_bullet edges can be selected
    fake_edges = [
        {"profile_fact_ids": ["C1"], "dossier_fact_ids": ["D1"], "reason": "Essay edge", "use_in": "essay", "strength": 0.9},
        {"profile_fact_ids": ["C1"], "dossier_fact_ids": ["D1"], "reason": "Bullet edge", "use_in": "cv_bullet", "strength": 0.8},
    ]
    set_clients_for_tests(FakeEdgeClient(fake_edges), FakeEdgeClient(fake_edges))

    listing = make_test_listing()
    dossier = make_test_dossier(degraded=True)
    facts = [Fact(id="C1", source="cv", category="work", text="Intern", sensitive=False)]
    prefs = Preferences()

    edges, gaps = find_edges(listing, dossier, facts, prefs, RunContext(run_id="run_1"))
    assert len(edges) == 2

    # E1 has use_in="essay" -> NOT selected due to degraded dossier rule!
    assert edges[0].selected is False
    # E2 has use_in="cv_bullet" -> selected!
    assert edges[1].selected is True
