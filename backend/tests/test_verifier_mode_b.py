"""Tests for Verifier Mode B self-healing enforcement loop (Task B15)."""
import json
import pytest

from app import db
from app.agents.verifier import audit, challenge, verify_mode_b
from app.errors import RunContext
from app.llm import set_clients_for_tests
from app.models import (
    Claim,
    Listing,
    RemovedClaim,
    Segment,
    TailoredOutput,
    VerificationReport,
)


class DummyChoice:
    def __init__(self, content: str):
        self.message = type("DummyMsg", (), {"content": content})()


class DummyResp:
    def __init__(self, content: str):
        self.choices = [DummyChoice(content)]
        self.usage = type("Usage", (), {"prompt_tokens": 50, "completion_tokens": 50})()


class ScriptedClient:
    def __init__(self, responses: list[str]):
        self.responses = list(responses)
        self.calls = []

    @property
    def chat(self):
        return self

    @property
    def completions(self):
        return self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.responses:
            return DummyResp(self.responses.pop(0))
        return DummyResp("{}")


@pytest.fixture(autouse=True)
def setup_db(tmp_path, monkeypatch):
    test_db = tmp_path / "verifier_b_test.db"
    monkeypatch.setenv("TEST_DB_PATH", str(test_db))
    monkeypatch.setenv("RETRY_SLEEP_SECONDS", "0")
    db.init_db()
    yield test_db


def make_test_listing() -> Listing:
    return Listing.model_validate({
        "id": "mock_portal_masters",
        "name": "Demo Masters Award",
        "is_mock": True,
        "provider": "University of Demo",
        "country": "UK",
        "level": "masters",
        "fields": ["computer engineering"],
        "min_gpa": 3.5,
        "gpa_scale": 5.0,
        "eligible_nationalities": ["Nigeria"],
        "deadline": "2026/12/01",
        "channel": "portal_form",
        "criteria_text": "Engineering focus and smart grid systems.",
        "essay_prompt": "Explain your background.",
        "essay_word_limit": 300,
        "source_url": "http://localhost:8000/portal/about/mock",
    })


def test_verify_mode_b_unsupported_then_fixed_round_1():
    """Unsupported claim in round 1 gets revised and verified as supported in round 2."""
    listing = make_test_listing()
    sources = {"C1": "5 months internship at BrightGrid Solar testing 12 sensor boards"}
    ctx = RunContext(run_id="run_test", app_id="app_1", mode="B")

    tailored = TailoredOutput(
        cv_summary=[],
        cv_bullets=[],
        essay=[
            Segment(text="I developed firmware during my internship.", source_ids=["C1"]),
            Segment(text="I bring years of professional experience in solar.", source_ids=["C1"]),
        ],
    )

    # Sequence of LLM calls in Mode B:
    # 1. Round 1 extract
    extract_r1 = json.dumps({
        "claims": [
            {"text": "I developed firmware during my internship.", "section": "essay", "segment_index": 0},
            {"text": "I bring years of professional experience in solar.", "section": "essay", "segment_index": 1},
        ]
    })
    # 2. Round 1 judge (claim 2 unsupported)
    judge_r1 = json.dumps({
        "verdicts": [
            {"claim_id": "CL1", "verdict": "supported", "reason": "Consistent with internship."},
            {"claim_id": "CL2", "verdict": "unsupported", "reason": "Duration trap: 5 months is not years."},
        ]
    })
    # 3. tailor_revise call (revises segment index 1)
    revise_res = json.dumps({
        "revisions": [
            {
                "section": "essay",
                "segment_index": 1,
                "text": "During my 5-month internship, I tested solar sensor boards.",
                "source_ids": ["C1"],
            }
        ]
    })
    # 4. Round 2 extract
    extract_r2 = json.dumps({
        "claims": [
            {"text": "I developed firmware during my internship.", "section": "essay", "segment_index": 0},
            {"text": "During my 5-month internship, I tested solar sensor boards.", "section": "essay", "segment_index": 1},
        ]
    })
    # 5. Round 2 judge (both supported now)
    judge_r2 = json.dumps({
        "verdicts": [
            {"claim_id": "CL1", "verdict": "supported", "reason": "Consistent with internship."},
            {"claim_id": "CL2", "verdict": "supported", "reason": "Exact 5-month duration matches source."},
        ]
    })
    # 6. Challenger call (defend both)
    challenge_res = json.dumps({
        "challenges": [
            {"claim_id": "CL1", "outcome": "defend", "reason": "Grounded."},
            {"claim_id": "CL2", "outcome": "defend", "reason": "Grounded."},
        ]
    })

    fake = ScriptedClient([extract_r1, judge_r1, revise_res, extract_r2, judge_r2, challenge_res])
    set_clients_for_tests(primary=fake, fallback=None)

    final_tailored, report = verify_mode_b(tailored, sources, listing, ctx)

    assert report.unsupported_before == 1
    assert report.unsupported_final == 0
    assert report.rounds == 2
    assert len(report.removed_claims) == 0
    assert "5-month internship" in final_tailored.essay[1].text


def test_verify_mode_b_unsupported_twice_then_removed():
    """Claim unsupported across revision rounds gets removed with a RemovedClaim."""
    listing = make_test_listing()
    sources = {"C1": "Internship at BrightGrid"}
    ctx = RunContext(run_id="run_test", app_id="app_1", mode="B")

    tailored = TailoredOutput(
        cv_summary=[],
        cv_bullets=[],
        essay=[
            Segment(text="I am president of the international solar federation.", source_ids=["C1"]),
        ],
    )

    # 1. Round 1 extract & judge (unsupported)
    ext1 = json.dumps({"claims": [{"text": "I am president.", "section": "essay", "segment_index": 0}]})
    jdg1 = json.dumps({"verdicts": [{"claim_id": "CL1", "verdict": "unsupported", "reason": "Title trap."}]})
    # 2. Revise attempt
    rev1 = json.dumps({"revisions": [{"section": "essay", "segment_index": 0, "text": "I lead the federation.", "source_ids": ["C1"]}]})
    # 3. Round 2 extract & judge (still unsupported)
    ext2 = json.dumps({"claims": [{"text": "I lead the federation.", "section": "essay", "segment_index": 0}]})
    jdg2 = json.dumps({"verdicts": [{"claim_id": "CL1", "verdict": "unsupported", "reason": "Title trap still."}]})
    # 4. Revise attempt round 2
    rev2 = json.dumps({"revisions": [{"section": "essay", "segment_index": 0, "text": "I am head of the federation.", "source_ids": ["C1"]}]})
    # 5. Round 3 extract & judge (still unsupported -> triggers removal)
    ext3 = json.dumps({"claims": [{"text": "I am head of the federation.", "section": "essay", "segment_index": 0}]})
    jdg3 = json.dumps({"verdicts": [{"claim_id": "CL1", "verdict": "unsupported", "reason": "Still unsupported."}]})
    # 6. Challenge call (empty because no supported claims left)
    chall = json.dumps({"challenges": []})

    fake = ScriptedClient([ext1, jdg1, rev1, ext2, jdg2, rev2, ext3, jdg3, chall])
    set_clients_for_tests(primary=fake, fallback=None)

    final_tailored, report = verify_mode_b(tailored, sources, listing, ctx)

    assert report.unsupported_before == 1
    assert report.unsupported_final == 0
    assert len(report.removed_claims) >= 1
    assert final_tailored.essay[0].status == "removed"


def test_verify_mode_b_sensitive_scan_removes_text():
    """Final sensitive scan removes segments containing sensitive stems."""
    listing = make_test_listing()
    sources = {"C1": "Studied engineering"}
    ctx = RunContext(run_id="run_test", app_id="app_1", mode="B")

    tailored = TailoredOutput(
        cv_summary=[],
        cv_bullets=[],
        essay=[
            Segment(text="I faced extreme family income hardship during studies.", source_ids=["C1"]),
        ],
    )

    # Extract & Judge mark as supported
    ext = json.dumps({"claims": [{"text": "I faced hardship.", "section": "essay", "segment_index": 0}]})
    jdg = json.dumps({"verdicts": [{"claim_id": "CL1", "verdict": "supported", "reason": "Supported."}]})
    chall = json.dumps({"challenges": [{"claim_id": "CL1", "outcome": "defend", "reason": "Defended."}]})

    fake = ScriptedClient([ext, jdg, chall])
    set_clients_for_tests(primary=fake, fallback=None)

    final_tailored, report = verify_mode_b(tailored, sources, listing, ctx)

    # Segment must be removed due to "income hardship" sensitive stem
    assert final_tailored.essay[0].status == "removed"
    assert any("sensitive detail" in rc.reason for rc in report.removed_claims)
    assert report.unsupported_final == 0
