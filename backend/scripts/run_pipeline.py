"""Pipeline CLI runner: executes end-to-end runs and logs evidence."""
import json
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

# 1. Parse positional arguments
mode = sys.argv[1].upper() if len(sys.argv) > 1 else "B"
top_n = int(sys.argv[2]) if len(sys.argv) > 2 else 2
tags_arg = sys.argv[3] if len(sys.argv) > 3 else f"run_{mode}"
tags = [t.strip() for t in tags_arg.split(",") if t.strip()]

# 2. Initialize Neatlogs tracing BEFORE importing agents or creating clients
from app.tracing import init_tracing, shutdown_tracing
init_tracing(tags=tags)

# 3. Import app modules
from app import db
from app.coordinator import execute_run
from app.errors import RunContext

# Initialize DB tables
db.init_db()

# Check if facts exist; if not, seed synthetic persona
facts = db.get_facts()
if not facts:
    from app.agents.intake import run_intake
    data_dir = backend_dir / "data" / "synthetic"
    cv_text = (data_dir / "cv.txt").read_text(encoding="utf-8")
    tr_text = (data_dir / "transcript.txt").read_text(encoding="utf-8")
    prefs = json.loads((data_dir / "preferences.json").read_text(encoding="utf-8"))
    vault = json.loads((data_dir / "vault.json").read_text(encoding="utf-8"))
    payload = {
        "cv_text": cv_text,
        "transcript_text": tr_text,
        "preferences": prefs,
        "vault_sections": vault,
    }
    intake_res = run_intake(payload, RunContext())
    print(f"Loaded synthetic persona: {len(intake_res['facts'])} facts extracted.")

# 4. Create run and execute synchronously
run_id = db.create_run(mode, top_n)
print(f"Executing run {run_id} in Mode {mode} (top_n={top_n}, tags={tags})...")

try:
    execute_run(run_id)
except Exception as e:
    print(f"Run {run_id} failed with error: {e}", file=sys.stderr)
    db.finish_run(run_id, "failed")
    shutdown_tracing()
    sys.exit(1)

# Retrieve finished run & metrics
run_data = db.get_run(run_id)
metrics = run_data.get("metrics") or {}
print("\n=== RUN METRICS ===")
print(json.dumps(metrics, indent=2))

# 5. Build application summary & write evidence file
apps = db.list_applications(run_id)
app_summaries = []
for a in apps:
    vr = a.get("verification") or {}
    app_summaries.append({
        "id": a["id"],
        "listing_id": a["listing_id"],
        "status": a["status"],
        "unsupported_before": vr.get("unsupported_before", 0),
        "unsupported_final": vr.get("unsupported_final", 0),
        "claims_removed": len(vr.get("removed_claims", [])),
        "claims_overturned": len(vr.get("overturned_claims", [])),
    })

evidence_dir = backend_dir.parent / "docs" / "evidence"
evidence_dir.mkdir(parents=True, exist_ok=True)

# Count existing run_{mode}_*.json files to determine n
existing_files = list(evidence_dir.glob(f"run_{mode}_*.json"))
n = len(existing_files) + 1
evidence_file = evidence_dir / f"run_{mode}_{n}.json"

evidence_payload = {
    "run_id": run_id,
    "mode": mode,
    "tags": tags,
    "metrics": metrics,
    "applications": app_summaries,
    "trace_url": run_data.get("trace_url"),
}

evidence_file.write_text(json.dumps(evidence_payload, indent=2), encoding="utf-8")
print(f"\nEvidence written to: {evidence_file}")

# 6. Flush and shutdown tracing
shutdown_tracing()
print("Run finished successfully.")
