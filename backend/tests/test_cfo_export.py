import json
from pathlib import Path
import pytest
from scripts.export_cfo import read_run, export_bundle


def save_run(tmp_path: Path, metrics: dict) -> Path:
    path = tmp_path / "run.json"
    path.write_text(json.dumps({"run_id": "fictional_test", "metrics": metrics,
        "applications": [{"status": "prepared", "essay": "PRIVATE"}, {"status": "matched"}]}))
    return path


def test_missing_usage_is_unknown(tmp_path: Path) -> None:
    row = read_run(save_run(tmp_path, {"llm_calls": 0, "tokens_total": 0, "cost_usd": 0}))
    assert row["cost_per_completed_application_usd"] is None
    assert row["measurement_status"] == "usage_unavailable"


def test_cost_and_privacy(tmp_path: Path) -> None:
    path = save_run(tmp_path, {"llm_calls": 2, "tokens_total": 100, "cost_usd": 0.25})
    export_bundle([path], tmp_path / "export")
    manifest = (tmp_path / "export/model_inputs.json").read_text()
    assert "PRIVATE" not in manifest
    row = json.loads(manifest)["evidence"][0]
    assert row["completed_applications"] == 1
    assert row["cost_per_completed_application_usd"] == 0.25


@pytest.mark.parametrize("cost", [-1, float("nan"), float("inf"), None, True])
def test_invalid_cost(tmp_path: Path, cost: object) -> None:
    row = read_run(save_run(tmp_path, {"llm_calls": 2, "tokens_total": 100, "cost_usd": cost}))
    assert row["cost_per_completed_application_usd"] is None
