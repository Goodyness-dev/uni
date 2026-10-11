import os
import tempfile
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app import db

client = TestClient(app)


@pytest.fixture(autouse=True)
def temp_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        temp_path = f.name
    os.environ["TEST_DB_PATH"] = temp_path
    db.init_db()
    yield
    if os.path.exists(temp_path):
        os.remove(temp_path)
    os.environ.pop("TEST_DB_PATH", None)


def test_failure_flags_endpoints():
    # Initial read
    resp = client.get("/api/failure_flags")
    assert resp.status_code == 200
    data = resp.json()
    assert "flags" in data
    assert "remaining" in data
    assert "llm_429" in data["flags"]

    # Set flag
    post_resp = client.post(
        "/api/failure_flags",
        json={"flags": {"llm_429": True, "bad_json": True}, "counts": {"llm_429": 2, "bad_json": 1}},
    )
    assert post_resp.status_code == 200
    updated = post_resp.json()
    assert updated["flags"]["llm_429"] is True
    assert updated["remaining"]["llm_429"] == 2
    assert updated["flags"]["bad_json"] is True
    assert updated["remaining"]["bad_json"] == 1
