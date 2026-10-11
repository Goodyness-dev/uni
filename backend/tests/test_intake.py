"""Tests for the Intake agent (Task B07)."""
import base64
import io
import json
import pytest
from reportlab.pdfgen import canvas

from app import db
from app.agents.intake import run_intake
from app.config import settings
from app.errors import RunContext
from app.llm import set_clients_for_tests


class DummyChoice:
    def __init__(self, content: str):
        self.message = type("DummyMsg", (), {"content": content})()


class DummyUsage:
    prompt_tokens = 50
    completion_tokens = 50


class DummyResp:
    def __init__(self, content: str):
        self.choices = [DummyChoice(content)]
        self.usage = DummyUsage()


class FakeIntakeClient:
    def __init__(self, response_generator=None):
        self.response_generator = response_generator

    @property
    def chat(self):
        return self

    @property
    def completions(self):
        return self

    def create(self, **kwargs):
        messages = kwargs.get("messages", [])
        user_msg = messages[-1]["content"] if messages else ""
        if self.response_generator:
            content = self.response_generator(user_msg)
        else:
            # Default mock extraction: echo facts from the prompt
            if "Section: hardships" in user_msg:
                content = json.dumps({"facts": [{"category": "hardships", "text": "Family income was low during second year", "sensitive": False}]})
            elif "Section: leadership" in user_msg:
                content = json.dumps({"facts": [{"category": "leadership", "text": "Assistant coordinator of Tech Club for 120 participants", "sensitive": False}]})
            elif "Transcript" in user_msg or "CGPA" in user_msg:
                content = json.dumps({"facts": [{"category": "grades", "text": "CGPA 4.30 out of 5.00", "sensitive": False}]})
            else:
                content = json.dumps({"facts": [
                    {"category": "work", "text": "Embedded Systems Intern for 5 months", "sensitive": False},
                    {"category": "sports", "text": "Played football for 4 years", "sensitive": False},
                ]})
        return DummyResp(content)


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path, monkeypatch):
    test_db = str(tmp_path / "test_intake.db")
    monkeypatch.setenv("TEST_DB_PATH", test_db)
    db.init_db()


def test_fact_ids_and_sources():
    set_clients_for_tests(FakeIntakeClient(), FakeIntakeClient())

    payload = {
        "cv_text": "Embedded Systems Intern for 5 months in 2024. Played football for 4 years.",
        "transcript_text": "Transcript summary: CGPA 4.30 out of 5.00",
        "vault_sections": {
            "leadership": "Assistant coordinator of Tech Club for 120 participants",
            "hardships": "Family income was low during second year",
        },
    }

    result = run_intake(payload, RunContext(run_id="run_20261011_001"))
    facts = result["facts"]
    counts = result["counts"]

    # Verify ID prefixes
    cv_facts = [f for f in facts if f.source == "cv"]
    tr_facts = [f for f in facts if f.source == "transcript"]
    v_facts = [f for f in facts if f.source == "vault"]

    assert all(f.id.startswith("C") for f in cv_facts)
    assert all(f.id.startswith("T") for f in tr_facts)
    assert all(f.id.startswith("P") for f in v_facts)

    assert counts["cv"] == len(cv_facts)
    assert counts["transcript"] == len(tr_facts)
    assert counts["vault"] == len(v_facts)

    # Hardship fact must be sensitive (income keyword or hardships category)
    hardship = next(f for f in v_facts if "income" in f.text.lower())
    assert hardship.sensitive is True


def test_deterministic_number_check_drops_hallucinations():
    def altered_generator(user_text: str):
        # Hallucinate a number: original text says 5 months, model outputs 10 months
        return json.dumps({
            "facts": [
                {"category": "work", "text": "Embedded Systems Intern for 10 months", "sensitive": False},
                {"category": "work", "text": "Embedded Systems Intern for 5 months", "sensitive": False},
            ]
        })

    set_clients_for_tests(FakeIntakeClient(altered_generator), FakeIntakeClient(altered_generator))

    payload = {"cv_text": "Embedded Systems Intern for 5 months in 2024."}
    result = run_intake(payload, RunContext())

    facts = result["facts"]
    # The 10 months fact must be dropped; the 5 months fact survives
    assert len(facts) == 1
    assert "5 months" in facts[0].text
    assert "Dropped a fact whose numbers were not in the source" in result["warnings"]


def test_duplicate_removal():
    def duplicate_generator(user_text: str):
        return json.dumps({
            "facts": [
                {"category": "sports", "text": "Played football for 4 years", "sensitive": False},
                {"category": "sports", "text": "  played FOOTBALL for 4   years  ", "sensitive": False},
            ]
        })

    set_clients_for_tests(FakeIntakeClient(duplicate_generator), FakeIntakeClient(duplicate_generator))

    payload = {"cv_text": "Played football for 4 years."}
    result = run_intake(payload, RunContext())
    assert len(result["facts"]) == 1


def test_pdf_base64_parsing():
    set_clients_for_tests(FakeIntakeClient(), FakeIntakeClient())

    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    # Generate text >= 200 chars to avoid warning
    text_content = (
        "Tobi Adeyemi BSc Computer Engineering with 5 months internship and solar projects. "
        "Dean's list for 2 sessions. Embedded Systems Intern for 5 months. Played football for 4 years. "
        "SunTrack low cost solar panel monitoring system built with ESP32 microcontroller and wireless sensors."
    )
    c.drawString(100, 750, text_content)
    c.save()

    pdf_b64 = base64.b64encode(buf.getvalue()).decode()
    payload = {"cv_pdf_base64": pdf_b64}

    result = run_intake(payload, RunContext())
    assert len(result["facts"]) >= 1
    assert result["counts"]["cv"] >= 1
