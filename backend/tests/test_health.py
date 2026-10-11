import os
import tempfile
from fastapi.testclient import TestClient

from app.main import app
from app.config import load_env_file, settings

client = TestClient(app)


def test_health_endpoint_contract() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "llm_primary" in data
    assert "llm_fallback" in data
    assert "telegram" in data
    assert "neatlogs" in data
    assert "smtp" in data
    assert "crustdata" in data
    assert "demo_mode" in data
    assert data["neatlogs"] == "configured"  # Set in backend/.env


def test_env_loader_does_not_override_existing() -> None:
    os.environ["EXISTING_KEY_TEST"] = "original_val"
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".env") as f:
        f.write("EXISTING_KEY_TEST=new_val\nNEW_KEY_TEST=injected_val\n# comment\n")
        temp_path = f.name

    try:
        load_env_file(temp_path)
        assert os.environ["EXISTING_KEY_TEST"] == "original_val"
        assert os.environ["NEW_KEY_TEST"] == "injected_val"
    finally:
        os.remove(temp_path)
        os.environ.pop("EXISTING_KEY_TEST", None)
        os.environ.pop("NEW_KEY_TEST", None)
