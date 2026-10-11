"""Seed synthetic persona facts and preferences into the SQLite database."""
import json
import sys
from pathlib import Path

# Add backend directory to sys.path so app imports work
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.agents.intake import run_intake
from app.config import settings
from app.db import init_db
from app.errors import RunContext


def load_persona_payload() -> dict:
    """Reads synthetic persona files and constructs the intake payload."""
    data_dir = backend_dir / "data" / "synthetic"
    cv_text = (data_dir / "cv.txt").read_text(encoding="utf-8")
    transcript_text = (data_dir / "transcript.txt").read_text(encoding="utf-8")
    preferences = json.loads((data_dir / "preferences.json").read_text(encoding="utf-8"))
    vault_sections = json.loads((data_dir / "vault.json").read_text(encoding="utf-8"))

    return {
        "cv_text": cv_text,
        "transcript_text": transcript_text,
        "preferences": preferences,
        "vault_sections": vault_sections,
    }


def main() -> None:
    print(f"Loading synthetic persona from backend/data/synthetic...")
    init_db()
    payload = load_persona_payload()
    result = run_intake(payload, RunContext())
    counts = result["counts"]
    total = len(result["facts"])
    print(f"Intake complete: {total} total facts extracted.")
    print(f"  CV: {counts['cv']}, Transcript: {counts['transcript']}, Vault: {counts['vault']}")
    if result["warnings"]:
        print(f"Warnings ({len(result['warnings'])}):")
        for w in result["warnings"]:
            print(f"  - {w}")


if __name__ == "__main__":
    main()
