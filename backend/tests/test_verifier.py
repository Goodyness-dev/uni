"""Tests for Verifier agent, deterministic checking, judging, and challenger (Task B12)."""
import json
import pytest

from app import db
from app.agents.verifier import audit, challenge, deterministic_check, verify_mode_a
from app.config import settings
from app.errors import RunContext
from app.llm import set_clients_for_tests
from app.models import Segment, TailoredOutput


class DummyChoice:
    def __init__(self, content: str):
        self.message = type("DummyMsg", (), {"content": content})()


class DummyResp:
    def __init__(self, content: str):
        self.choices = [DummyChoice(content)]
        self.usage = type("Usage", (), {"prompt_tokens": 50, "completion_tokens": 50})()


class FakeVerifierClient:
    def __init__(self, extract_claims=None, judge_verdicts=None, challenges=None):
        self.extract_claims = extract_claims
        self.judge_verdicts = judge_verdicts
        self.challenges = challenges

    @property
    def chat(self):
        return self

    @property
    def completions(self):
        return self

    def create(self, **kwargs):
        messages = kwargs.get("messages", [])
        system = messages[0]["content"] if messages else ""

        if "split" in system.lower() or "atomic claims" in system.lower():
            claims = self.extract_claims or [{"text": "Wrote solar firmware.", "section": "essay", "segment_index": 0}]
            content = json.dumps({"claims": claims})
        elif "judge" in system.lower() or "fact checker" in system.lower():
            verdicts = self.judge_verdicts or [{"claim_id": "CL1", "verdict": "supported", "reason": "Accurate"}]
            content = json.dumps({"verdicts": verdicts})
        elif "skeptical" in system.lower() or "challenge" in system.lower() or "committee" in system.lower():
            chals = self.challenges or [{"claim_id": "CL1", "outcome": "defend", "reason": "Solid evidence"}]
            content = json.dumps({"challenges": chals})
        else:
            content = "{}"
        return DummyResp(content)


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path, monkeypatch):
    test_db = str(tmp_path / "test_verifier.db")
    monkeypatch.setenv("TEST_DB_PATH", test_db)
    db.init_db()


def test_deterministic_check_numbers_and_entities():
    sources = {
        "C1": "Embedded Systems Intern, BrightGrid Solar, 5 months in 2024.",
        "C2": "Tested the firmware on 12 sensor boards.",
    }

    # 1. Matching numbers: passes
    assert deterministic_check("Tested on 12 sensor boards.", ["C2"], sources) is True

    # 2. Number mismatch: fails
    assert deterministic_check("Tested on 24 sensor boards.", ["C2"], sources) is False

    # 3. Number words normalized: "five" matches "5"
    assert deterministic_check("Internship lasted five months.", ["C1"], sources) is True

    # 4. Unknown entity: "Microsoft" fails
    assert deterministic_check("Interned at Microsoft for five months.", ["C1"], sources) is False

    # 5. Missing source ID: fails
    assert deterministic_check("Tested on 12 sensor boards.", ["C99"], sources) is False


def test_audit_verdict_combinations():
    # 2 claims: CL1 is supported + deterministic True; CL2 is supported + deterministic False (fails number check)
    extract_claims = [
        {"text": "Tested on 12 sensor boards.", "section": "essay", "segment_index": 0},
        {"text": "Tested on 99 sensor boards.", "section": "essay", "segment_index": 0},
    ]
    judge_verdicts = [
        {"claim_id": "CL1", "verdict": "supported", "reason": "Matches"},
        {"claim_id": "CL2", "verdict": "supported", "reason": "Matches"},
    ]
    client = FakeVerifierClient(extract_claims=extract_claims, judge_verdicts=judge_verdicts)
    set_clients_for_tests(client, client)

    sources = {"C1": "Tested on 12 sensor boards."}
    tailored = TailoredOutput(
        cv_summary=[],
        cv_bullets=[],
        essay=[Segment(text="Sentence with claims", source_ids=["C1"], status="supported")],
    )

    report = audit(tailored, sources, RunContext())
    assert len(report.claims) == 2

    # CL1: judge supported + det True -> supported
    assert report.claims[0].verdict == "supported"
    assert report.claims[0].deterministic_pass is True

    # CL2: judge supported + det False (99 not in source) -> downgraded to partial!
    assert report.claims[1].verdict == "partial"
    assert report.claims[1].deterministic_pass is False


def test_challenge_overturns_overreaching_claims():
    extract_claims = [{"text": "Led engineering team.", "section": "essay", "segment_index": 0}]
    judge_verdicts = [{"claim_id": "CL1", "verdict": "supported", "reason": "Good"}]
    challenges = [{"claim_id": "CL1", "outcome": "overturn", "reason": "Title upgrade: was assistant coordinator not leader"}]
    client = FakeVerifierClient(extract_claims=extract_claims, judge_verdicts=judge_verdicts, challenges=challenges)
    set_clients_for_tests(client, client)

    sources = {"C1": "Led engineering team."}
    tailored = TailoredOutput(
        cv_summary=[],
        cv_bullets=[],
        essay=[Segment(text="Led engineering team.", source_ids=["C1"], status="supported")],
    )

    report = audit(tailored, sources, RunContext(run_id="run_1"))
    assert report.claims[0].verdict == "supported"

    challenged_report = challenge(report, sources, RunContext(run_id="run_1"))
    assert challenged_report.claims[0].overturned is True
    assert len(challenged_report.overturned_claims) == 1
    assert "Title upgrade" in challenged_report.overturned_claims[0].reason


def test_verify_mode_a_measurement_invariance():
    client = FakeVerifierClient()
    set_clients_for_tests(client, client)

    sources = {"C1": "Solar work."}
    tailored = TailoredOutput(
        cv_summary=[Segment(text="Summary text", source_ids=["C1"], status="supported")],
        cv_bullets=[Segment(text="Bullet text", source_ids=["C1"], status="supported")],
        essay=[Segment(text="Essay text", source_ids=["C1"], status="supported")],
    )

    t_out, report = verify_mode_a(tailored, sources, RunContext())

    # Mode A invariant: tailored text is 100% untouched
    assert t_out.essay[0].text == "Essay text"
    assert t_out.cv_bullets[0].text == "Bullet text"
    assert report.unsupported_final == report.unsupported_before
