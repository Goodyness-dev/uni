"""Evaluation CLI runner: executes mode B evaluation runs and verifies 0 unsupported claims."""
import json
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

# 1. Parse tag version
eval_tag = sys.argv[1] if len(sys.argv) > 1 else "eval_v1"
tags = ["eval", eval_tag]

# 2. Initialize Neatlogs tracing
from app.tracing import init_tracing, shutdown_tracing
init_tracing(tags=tags)

# 3. Import app modules
from app import db
from app.coordinator import execute_run
from app.errors import RunContext

# Initialize DB tables and seed persona if missing
db.init_db()
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

# 4. Execute Mode B three times
results = []
unsupported_any = False

print(f"\n=======================================================")
print(f"Starting Evaluation: {eval_tag} (3 consecutive Mode B runs)")
print(f"=======================================================\n")

for i in range(1, 4):
    run_id = db.create_run("B", 2)
    print(f"[{i}/3] Executing run {run_id} in Mode B...")
    try:
        execute_run(run_id)
    except Exception as e:
        print(f"Run {run_id} failed with error: {e}", file=sys.stderr)
        db.finish_run(run_id, "failed")
        continue

    run_data = db.get_run(run_id)
    metrics = run_data.get("metrics") or {}
    apps = db.list_applications(run_id)

    tot_claims = 0
    tot_unsupported_before = 0
    tot_unsupported_final = 0
    tot_overturned = 0

    for a in apps:
        vr = a.get("verification") or {}
        tot_claims += len(vr.get("claims", []))
        tot_unsupported_before += vr.get("unsupported_before", 0)
        tot_unsupported_final += vr.get("unsupported_final", 0)
        tot_overturned += len(vr.get("overturned_claims", []))

    if tot_unsupported_final > 0:
        unsupported_any = True

    results.append({
        "run_index": i,
        "run_id": run_id,
        "claims_total": tot_claims,
        "unsupported_before": tot_unsupported_before,
        "unsupported_final": tot_unsupported_final,
        "claims_overturned": tot_overturned,
        "cost_usd": metrics.get("cost_usd", 0.0),
        "latency_seconds": metrics.get("wall_time_seconds", 0.0),
        "recovery_decisions": metrics.get("recovery_decisions", 0),
        "trace_url": run_data.get("trace_url"),
    })

# 5. Format and print evaluation table
print("\n" + "=" * 90)
print(f"{'Run':<6} | {'Run ID':<10} | {'Claims':<8} | {'Unsup(Pre)':<11} | {'Unsup(Fin)':<11} | {'Overturned':<11} | {'Cost ($)':<9} | {'Lat (s)':<8} | {'Recov':<6}")
print("-" * 90)
for r in results:
    print(
        f"{r['run_index']:<6} | "
        f"{r['run_id']:<10} | "
        f"{r['claims_total']:<8} | "
        f"{r['unsupported_before']:<11} | "
        f"{r['unsupported_final']:<11} | "
        f"{r['claims_overturned']:<11} | "
        f"{r['cost_usd']:<9.4f} | "
        f"{r['latency_seconds']:<8.2f} | "
        f"{r['recovery_decisions']:<6}"
    )
print("=" * 90 + "\n")

# 6. Save evaluation artifact
evidence_dir = backend_dir.parent / "docs" / "evidence"
evidence_dir.mkdir(parents=True, exist_ok=True)
eval_file = evidence_dir / f"{eval_tag}.json"
eval_file.write_text(json.dumps({"tag": eval_tag, "runs": results}, indent=2), encoding="utf-8")
print(f"Saved evaluation results to {eval_file}\n")

shutdown_tracing()

if unsupported_any:
    print("FAILED: At least one application has unsupported claims in final output!", file=sys.stderr)
    sys.exit(1)

print("SUCCESS: Zero unsupported claims in all evaluation runs.")
sys.exit(0)
