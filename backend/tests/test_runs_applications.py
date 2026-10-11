"""Tests for runs and applications API routes conforming to docs/06_API_CONTRACT.md."""
import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import app


@pytest.fixture(autouse=True)
def setup_db(tmp_path, monkeypatch):
    test_db = tmp_path / "api_test.db"
    monkeypatch.setenv("TEST_DB_PATH", str(test_db))
    monkeypatch.setenv("RETRY_SLEEP_SECONDS", "0")
    monkeypatch.setattr("app.coordinator.start_run_thread", lambda r_id: None)
    monkeypatch.setattr("app.routers.runs.start_run_thread", lambda r_id: None)
    db.init_db()
    yield test_db


@pytest.fixture
def client():
    return TestClient(app)


def test_create_run_no_facts_error(client):
    """POST /api/runs returns 400 when no facts exist."""
    resp = client.post("/api/runs", json={"mode": "A", "top_n": 2})
    assert resp.status_code == 400


def test_create_run_and_get_endpoints(client, monkeypatch):
    """POST /api/runs creates run, returns 202, and GET /api/runs/{id} returns full shape."""
    # Seed a fact
    db.replace_facts([{"id": "C1", "source": "cv", "category": "work", "text": "Engineer", "sensitive": False}])
    db.set_preferences({"full_name": "Tobi Adeyemi", "email": "tobi@test.com", "sensitive_consent": False})

    # Mock execute_run to prevent background execution
    monkeypatch.setattr("app.coordinator.start_run_thread", lambda r_id: None)

    resp = client.post("/api/runs", json={"mode": "A", "top_n": 2})
    assert resp.status_code == 202
    data = resp.json()
    assert "run_id" in data
    assert data["status"] == "running"
    run_id = data["run_id"]

    # GET /api/runs/{id}
    resp_get = client.get(f"/api/runs/{run_id}")
    assert resp_get.status_code == 200
    run_obj = resp_get.json()
    assert run_obj["run_id"] == run_id
    assert run_obj["mode"] == "A"
    assert run_obj["status"] == "running"
    assert "application_ids" in run_obj
    assert "started_at" in run_obj

    # GET /api/runs/latest
    resp_latest = client.get("/api/runs/latest")
    assert resp_latest.status_code == 200
    assert resp_latest.json()["run_id"] == run_id

    # GET /api/runs/{id}/events
    resp_events = client.get(f"/api/runs/{run_id}/events?after=0")
    assert resp_events.status_code == 200
    assert "events" in resp_events.json()
    assert "last_event_no" in resp_events.json()


def test_create_run_conflict_when_already_running(client, monkeypatch):
    """POST /api/runs returns 409 when a run is already running."""
    db.replace_facts([{"id": "C1", "source": "cv", "category": "work", "text": "Engineer", "sensitive": False}])
    db.set_preferences({"full_name": "Tobi Adeyemi"})
    db.create_run("A", 1)  # status is 'running'

    resp = client.post("/api/runs", json={"mode": "B", "top_n": 2})
    assert resp.status_code == 409


def test_resume_run_endpoints(client):
    """POST /api/runs/{id}/resume allows interrupted or failed runs only."""
    run_id = db.create_run("A", 1)
    db.finish_run(run_id, "interrupted")

    resp = client.post(f"/api/runs/{run_id}/resume")
    assert resp.status_code == 202
    assert resp.json()["status"] == "running"

    # Already running now: resume again should 409
    resp_conflict = client.post(f"/api/runs/{run_id}/resume")
    assert resp_conflict.status_code == 409


def test_applications_endpoints_contract(client):
    """GET /api/applications and GET /api/applications/{id} fulfill all contract keys."""
    run_id = db.create_run("A", 1)
    app_id = db.create_application(run_id, "mock_portal_masters", "portal_captcha")

    # List applications
    resp_list = client.get(f"/api/applications?run_id={run_id}")
    assert resp_list.status_code == 200
    apps = resp_list.json()["applications"]
    assert len(apps) == 1
    assert apps[0]["id"] == app_id
    assert "name" in apps[0]
    assert "is_mock" in apps[0]
    assert "fit_score" in apps[0]

    # Get single application - verify ALL contract keys
    resp_single = client.get(f"/api/applications/{app_id}")
    assert resp_single.status_code == 200
    app_data = resp_single.json()
    required_keys = [
        "id", "run_id", "listing", "status", "fit_score", "fit_reason",
        "failure_reason", "dossier", "edges", "tailored", "verification",
        "package", "handoff", "submission", "notifications", "timeline",
        "trace_url", "metrics",
    ]
    for key in required_keys:
        assert key in app_data, f"Missing required contract key: {key}"

    assert app_data["id"] == app_id
    assert app_data["listing"]["id"] == "mock_portal_masters"


def test_handoff_done_endpoint(client):
    """POST /api/applications/{id}/handoff/done transitions awaiting_user to submitting."""
    run_id = db.create_run("A", 1)
    app_id = db.create_application(run_id, "mock_portal_masters", "portal_captcha")

    # When not awaiting_user -> 409
    resp_err = client.post(f"/api/applications/{app_id}/handoff/done")
    assert resp_err.status_code == 409

    # Transition to awaiting_user
    db.set_status(app_id, "matched", "matched")
    db.set_status(app_id, "researched", "researched")
    db.set_status(app_id, "edges_selected", "edges")
    db.set_status(app_id, "tailored", "tailored")
    db.set_status(app_id, "verified", "verified")
    db.set_status(app_id, "ready", "ready")
    db.set_status(app_id, "submitting", "submitting")
    db.set_status(app_id, "awaiting_user", "handoff needed")

    resp_ok = client.post(f"/api/applications/{app_id}/handoff/done")
    assert resp_ok.status_code == 202
    assert resp_ok.json()["status"] == "submitting"

    app_row = db.get_application(app_id)
    assert app_row["status"] == "submitting"
