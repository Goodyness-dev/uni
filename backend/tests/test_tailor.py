"""Tests for Tailor agent, source grounding, and word limit enforcement (Task B11)."""
import json
import pytest

from app import db
from app.agents.tailor import build_sources, tailor_full, tailor_revise
from app.config import settings
from app.errors import LLMError, RunContext
from app.llm import set_clients_for_tests
from app.models import Dossier, DossierFact, Edge, Fact, Listing, Preferences, Segment, TailoredOutput


class DummyChoice:
    def __init__(self, content: str):
        self.message = type("DummyMsg", (), {"content": content})()


class DummyResp:
    def __init__(self, content: str):
        self.choices = [DummyChoice(content)]
        self.usage = type("Usage", (), {"prompt_tokens": 50, "completion_tokens": 50})()


class FakeTailorClient:
    def __init__(self, summary=None, bullets=None, essay=None, revisions=None):
        self.summary = summary or [{"text": "Graduated in computer engineering.", "source_ids": ["C1"]}]
        self.bullets = bullets or [{"text": "Wrote solar firmware.", "source_ids": ["C2"]}]
        self.essay = essay or [{"text": "I monitored rooftop solar panels.", "source_ids": ["C3", "D1"]}]
        self.revisions = revisions or []

    @property
    def chat(self):
        return self

    @property
    def completions(self):
        return self

    def create(self, **kwargs):
        messages = kwargs.get("messages", [])
        system = messages[0]["content"] if messages else ""
        if "revise" in system.lower():
            content = json.dumps({"revisions": self.revisions})
        else:
            content = json.dumps({
                "cv_summary": self.summary,
                "cv_bullets": self.bullets,
                "essay": self.essay,
            })
        return DummyResp(content)


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path, monkeypatch):
    test_db = str(tmp_path / "test_tailor.db")
    monkeypatch.setenv("TEST_DB_PATH", test_db)
    db.init_db()


def make_test_listing(**overrides) -> Listing:
    defaults = {
        "id": "mock_portal_masters",
        "name": "Aurora Energy AI Scholarship",
        "is_mock": True,
        "provider": "Aurora Technical University",
        "country": "UK",
        "level": "masters",
        "fields": ["energy systems"],
        "deadline": "2026/12/01",
        "channel": "portal_form",
        "criteria_text": "Solar energy machine learning.",
        "essay_prompt": "Describe your solar work.",
        "essay_word_limit": 20,  # Short limit for testing
    }
    defaults.update(overrides)
    return Listing.model_validate(defaults)


def test_build_sources_includes_core_and_selected_edges_only():
    listing = make_test_listing()
    facts = [
        Fact(id="C1", source="cv", category="education", text="BSc Computer Engineering", sensitive=False),
        Fact(id="C2", source="cv", category="work", text="Embedded solar intern", sensitive=False),
        Fact(id="P1", source="vault", category="sports", text="Played football for 4 years", sensitive=False),
        Fact(id="P2", source="vault", category="leadership", text="Tech club coordinator", sensitive=False),
        Fact(id="P3", source="vault", category="hardships", text="Income hardship", sensitive=True),
    ]
    dossier = Dossier(
        listing_id=listing.id,
        facts=[
            DossierFact(id="D1", topic="program_focus", text="Energy AI programme", source_url="", snippet="Energy AI", retrieved_at="2026/10/10"),
            DossierFact(id="D2", topic="values", text="Values community impact", source_url="", snippet="community", retrieved_at="2026/10/10"),
        ]
    )
    edges = [
        Edge(id="E1", profile_fact_ids=["P2"], dossier_fact_ids=["D1"], reason="Leadership", use_in="essay_opening", strength=0.9, selected=True),
        Edge(id="E2", profile_fact_ids=["P1"], dossier_fact_ids=["D2"], reason="Sports", use_in="essay_body", strength=0.4, selected=False),
    ]
    prefs = Preferences(sensitive_consent=False)

    sources = build_sources(listing, facts, dossier, edges, prefs)

    # Core facts included: C1 (education), C2 (work)
    assert "C1" in sources
    assert "C2" in sources
    # Selected edge facts included: P2 (profile), D1 (dossier)
    assert "P2" in sources
    assert "D1" in sources
    # Non-selected non-core facts NOT included: P1 (sports)
    assert "P1" not in sources
    # Sensitive facts NOT included: P3
    assert "P3" not in sources
    # Unselected dossier facts NOT included: D2
    assert "D2" not in sources


def test_tailor_full_drops_ungrounded_segments():
    # Model generates one segment citing valid C1, one citing fake C99
    essay = [
        {"text": "Valid sentence supported by C1.", "source_ids": ["C1"]},
        {"text": "Ungrounded sentence citing fake C99.", "source_ids": ["C99"]},
    ]
    set_clients_for_tests(FakeTailorClient(essay=essay), FakeTailorClient(essay=essay))

    listing = make_test_listing()
    sources = {"C1": "BSc Computer Engineering"}
    edges = []
    prefs = Preferences()

    tailored = tailor_full(listing, sources, edges, prefs, RunContext(run_id="run_1"))

    # Only valid segment survives
    assert len(tailored.essay) == 1
    assert tailored.essay[0].text == "Valid sentence supported by C1."
    assert tailored.essay[0].source_ids == ["C1"]


def test_tailor_full_enforces_word_limit():
    # Long essay exceeding 20 words limit
    long_essay = [
        {"text": "I worked on solar energy forecasting algorithms for five months at BrightGrid.", "source_ids": ["C1"]},  # 12 words
        {"text": "My final year project SunTrack monitored photovoltaic rooftop panels across three locations.", "source_ids": ["C1"]},  # 12 words
    ]
    set_clients_for_tests(FakeTailorClient(essay=long_essay), FakeTailorClient(essay=long_essay))

    listing = make_test_listing(essay_word_limit=15)
    sources = {"C1": "Solar work"}
    edges = []
    prefs = Preferences()

    tailored = tailor_full(listing, sources, edges, prefs, RunContext(run_id="run_1"))

    # Total words must be <= 15
    total_words = sum(len(s.text.split()) for s in tailored.essay)
    assert total_words <= 15
    # Second segment was truncated
    assert len(tailored.essay) == 1


def test_tailor_revise_updates_only_problem_segments():
    revisions = [
        {"section": "essay", "segment_index": 0, "text": "Revised supported sentence.", "source_ids": ["C1"]}
    ]
    set_clients_for_tests(FakeTailorClient(revisions=revisions), FakeTailorClient(revisions=revisions))

    listing = make_test_listing()
    sources = {"C1": "BSc Computer Engineering", "C2": "Intern"}
    tailored = TailoredOutput(
        cv_summary=[],
        cv_bullets=[Segment(text="Unchanged bullet", source_ids=["C2"], status="supported")],
        essay=[Segment(text="Problem sentence", source_ids=["C1"], status="supported")],
    )

    problem_segments = [{"section": "essay", "segment_index": 0, "reason": "overstated claim"}]
    revised = tailor_revise(listing, sources, tailored, problem_segments, RunContext())

    assert revised.essay[0].text == "Revised supported sentence."
    assert revised.cv_bullets[0].text == "Unchanged bullet"
