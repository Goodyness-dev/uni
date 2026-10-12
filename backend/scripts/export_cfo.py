"""Export aggregate run evidence for cfo.ai without applicant content."""
import argparse
import csv
import json
import math
from pathlib import Path


def read_run(path: Path) -> dict:
    run = json.loads(path.read_text(encoding="utf-8-sig"))
    metrics = run.get("metrics", {})
    completed = sum(a.get("status") in {"prepared", "submitted"} for a in run.get("applications", []))
    calls, tokens, cost = (metrics.get(k) for k in ("llm_calls", "tokens_total", "cost_usd"))
    valid_cost = type(cost) in (int, float) and math.isfinite(cost) and cost >= 0
    measured = type(calls) in (int, float) and calls > 0 and type(tokens) in (int, float) and tokens > 0 and valid_cost and completed > 0
    return {"run_id": run["run_id"], "source_file": path.name, "mode": run.get("mode"),
            "completed_applications": completed, "tokens_total": tokens, "llm_calls": calls,
            "run_cost_usd": cost if valid_cost else None,
            "cost_per_completed_application_usd": cost / completed if measured else None,
            "measurement_status": "recorded_usage" if measured else "usage_unavailable",
            "trace_url": run.get("trace_url")}


def export_bundle(sources: list[Path], output: Path) -> None:
    rows = [read_run(path) for path in sources]
    output.mkdir(parents=True, exist_ok=True)
    with (output / "run_costs.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    manifest = {"evidence": rows, "live_cfo_page": None,
        "limitation": "Run-level LLM cost includes shared workflow overhead, not total service cost.",
        "assumptions": {"currency": "USD", "application_price": 4.99, "season_price": 19.99,
            "season_limit": 10, "starting_cash": 10000, "fixed_cost_monthly": 300,
            "review_minutes": 5, "review_hourly_cost": 10, "payment_percent": 0.029, "payment_fixed": 0.30},
        "required_inputs": ["Verified LLM unit cost", "Free-preview cost", "Refund rate", "Acquisition cost", "Hosting quote", "Actuals cutoff"],
        "scenarios": {"Main": {"paying_users": 150, "monthly_growth": 0.25},
            "Growth": {"paying_users": 400, "monthly_growth": 0.40},
            "Conservative": {"paying_users": 50, "monthly_growth": 0.15}}}
    (output / "model_inputs.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sources", nargs="+", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    export_bundle(args.sources, args.output)


if __name__ == "__main__":
    main()
