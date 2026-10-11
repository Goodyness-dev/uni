"""Tests for profile API endpoints (Task B07)."""
import json
import pytest
from fastapi.testclient import TestClient

from app import db
from app.config import settings
from app.llm import set_clients_for_tests
from app.main import app


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


class FakeClient:
    @property
    def chat(self):
        return self

    @property
    def completions(self):
        return self

    def create(self, **kwargs):
        content = json.dumps({"facts": [
            {"category": "work", "text": "Embedded Systems Intern for 5 months", "sensitive": False}
        ]})
        return DummyResp(content)


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path, monkeypatch):
    test_db = str(tmp_path / "test_profile_router.db")
    monkeypatch.setenv("TEST_DB_PATH", test_db)
    monkeypatch.setenv("DEMO_MODE", "true")
    db.init_db()
    set_clients_for_tests(FakeClient(), FakeClient())
    yield
    set_clients_for_tests(None, None)



def test_profile_intake_validation():
    client = TestClient(app)
    # Missing both cv_text and cv_pdf_base64 -> 400
    res = client.post("/api/profile/intake", json={"transcript_text": "hello"})
    assert res.status_code == 400


def test_profile_intake_and_facts_crud():
    client = TestClient(app)

    # 1. Intake POST
    payload = {
        "cv_text": "Embedded Systems Intern for 5 months in 2024.",
        "preferences": {
            "full_name": "Tobi Adeyemi",
            "email": "tobi.adeyemi@example.com",
            "level": "masters",
            "fields": ["computer engineering"],
            "countries": ["UK"],
            "funding": "full",
            "start_year": 2027,
            "nationality": "Nigeria",
            "gpa": 4.3,
            "gpa_scale": 5.0,
            "sensitive_consent": False,
        },
    }
    res = client.post("/api/profile/intake", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert "facts" in data
    assert "counts" in data
    assert len(data["facts"]) >= 1

    fact_id = data["facts"][0]["id"]

    # 2. GET /api/profile/facts
    res_get = client.get("/api/profile/facts")
    assert res_get.status_code == 200
    facts_data = res_get.json()
    assert len(facts_data["facts"]) >= 1
    assert facts_data["preferences"]["full_name"] == "Tobi Adeyemi"

    # 3. PATCH /api/profile/facts/{id}
    res_patch = client.patch(f"/api/profile/facts/{fact_id}", json={"text": "Updated fact text"})
    assert res_patch.status_code == 200
    assert res_patch.json()["text"] == "Updated fact text"

    # 4. POST /api/profile/facts (add vault fact)
    res_add = client.post("/api/profile/facts", json={"category": "volunteering", "text": "Taught 40 students"})
    assert res_add.status_code == 201
    added = res_add.json()
    assert added["id"].startswith("P")
    assert added["category"] == "volunteering"


def test_load_demo_endpoint(monkeypatch):
    client = TestClient(app)

    # With demo_mode True -> 201
    res = client.post("/api/profile/load_demo")
    assert res.status_code == 201
    data = res.json()
    assert "facts" in data
    assert "counts" in data

    # With demo_mode False -> 404
    monkeypatch.setenv("DEMO_MODE", "false")
    res_disabled = client.post("/api/profile/load_demo")
    assert res_disabled.status_code == 404
