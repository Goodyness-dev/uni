"""Coordinator: orchestrates the multi-agent pipeline with retries, recovery, and metrics."""
import threading
import time
from typing import Any, Callable

from app import db
from app.agents import edge_finder, matcher, researcher, scout, tailor, verifier
from app.config import settings
from app.errors import (
    BadJSONError,
    BlockerDetected,
    RateLimitError,
    RunContext,
    ScholarPilotError,
    TimeoutError_,
)
from app.models import (
    Dossier,
    Edge,
    Fact,
    Listing,
    Preferences,
    RunMetrics,
    TailoredOutput,
    VerificationReport,
)
from app import notify
from app.tracing import recovery_decision, workflow_span


def run_step(
    ctx: RunContext,
    step_name: str,
    fn: Callable[[], Any],
    fallback: Callable[[], Any] | None = None,
) -> Any:
    """Executes a pipeline step with idempotency checks, retries, and recovery decisions."""
    # 1. Idempotency check: if output already stored, return it
    if ctx.app_id:
        app_row = db.get_application(ctx.app_id)
        if app_row:
            if step_name == "research" and app_row.get("dossier"):
                return Dossier.model_validate(app_row["dossier"])
            elif step_name == "edges" and app_row.get("edges"):
                return [Edge.model_validate(e) for e in app_row["edges"]]
            elif step_name == "tailor" and app_row.get("tailored"):
                return TailoredOutput.model_validate(app_row["tailored"])
            elif step_name == "verify" and app_row.get("verification") and app_row.get("tailored"):
                return (
                    TailoredOutput.model_validate(app_row["tailored"]),
                    VerificationReport.model_validate(app_row["verification"]),
                )

    last_error: Exception | None = None
    max_attempts = 3

    for attempt in range(max_attempts):
        if attempt > 0 and settings.retry_sleep_seconds > 0:
            time.sleep(settings.retry_sleep_seconds * (2 ** (attempt - 1)))

        try:
            db.add_event(
                ctx.run_id,
                ctx.app_id,
                agent="coordinator",
                type_="step_started",
                message=f"Starting step {step_name} (attempt {attempt + 1})",
            )
            result = fn()
            db.add_event(
                ctx.run_id,
                ctx.app_id,
                agent="coordinator",
                type_="step_completed",
                message=f"Completed step {step_name}",
            )
            return result
        except (RateLimitError, TimeoutError_, BadJSONError) as err:
            last_error = err
            db.add_event(
                ctx.run_id,
                ctx.app_id,
                agent="coordinator",
                type_="retry",
                message=f"Retryable error on {step_name}: {err}",
            )
        except BlockerDetected as err:
            last_error = err
            db.add_event(
                ctx.run_id,
                ctx.app_id,
                agent="coordinator",
                type_="blocker_detected",
                message=str(err),
            )
            break
        except Exception as err:
            last_error = err
            # Check PortalError 5xx
            status = getattr(err, "status_code", None)
            if status and status >= 500:
                db.add_event(
                    ctx.run_id,
                    ctx.app_id,
                    agent="coordinator",
                    type_="retry",
                    message=f"Retryable HTTP {status} on {step_name}: {err}",
                )
            else:
                break

    # Attempts exhausted or fatal error: try fallback if available
    if fallback is not None:
        with recovery_decision(f"{step_name}_exhausted", ["retry", "fallback"]) as rd:
            rd.decide("fallback", f"Attempts exhausted for {step_name}, invoking fallback")
            db.add_event(
                ctx.run_id,
                ctx.app_id,
                agent="coordinator",
                type_="recovery_decision",
                message=f"Invoking fallback for {step_name}",
                data={"step": step_name, "chosen": "fallback", "reason": str(last_error)},
            )
            try:
                res = fallback()
                rd.finish("success")
                return res
            except Exception as fb_err:
                rd.finish("failed")
                last_error = fb_err

    # No fallback or fallback failed: mark application failed
    if ctx.app_id:
        err_msg = str(last_error) if last_error else f"Step {step_name} failed"
        db.update_application(ctx.app_id, failure_reason=err_msg)
        try:
            db.set_status(ctx.app_id, "failed", f"{step_name} failed: {err_msg}", agent="coordinator")
        except Exception:
            pass
        db.add_event(
            ctx.run_id,
            ctx.app_id,
            agent="coordinator",
            type_="step_failed",
            message=err_msg,
        )

    return None


def compute_metrics(run_id: str) -> RunMetrics:
    """Computes aggregated run metrics from application rows and event history."""
    apps = db.list_applications(run_id)
    events = db.list_events(run_id)

    claims_total = 0
    claims_unsupported = 0
    claims_removed = 0
    claims_overturned = 0
    unsupported_final = 0
    personal_refs_total = 0
    personal_refs_sourced = 0

    tokens_total = 0
    cost_usd = 0.0
    latency_seconds = 0.0
    llm_calls = 0
    llm_fallbacks = 0
    retries = 0
    recovery_decisions = 0

    for a in apps:
        vr = a.get("verification")
        if vr:
            claims = vr.get("claims", [])
            claims_total += len(claims)
            claims_unsupported += vr.get("unsupported_before", 0)
            claims_removed += len(vr.get("removed_claims", []))
            claims_overturned += len(vr.get("overturned_claims", []))
            unsupported_final += vr.get("unsupported_final", 0)

        tailored = a.get("tailored")
        if tailored:
            essay = tailored.get("essay", [])
            for seg in essay:
                text = seg.get("text", "").lower()
                s_ids = seg.get("source_ids", [])
                if any(w in text for w in ["programme", "program", "scholarship", "university", "faculty", "institution", "oxford", "cambridge", "fsu", "demo"]):
                    personal_refs_total += 1
                    if any(sid.startswith("D") for sid in s_ids):
                        personal_refs_sourced += 1

    for ev in events:
        ev_type = ev.get("type")
        data = ev.get("data", {})
        if ev_type == "retry":
            retries += 1
        elif ev_type == "recovery_decision":
            recovery_decisions += 1
        elif ev_type == "llm_fallback":
            llm_fallbacks += 1

        if "tokens_in" in data and "tokens_out" in data:
            llm_calls += 1
            tokens_total += data.get("tokens_in", 0) + data.get("tokens_out", 0)
            cost_usd += data.get("cost_usd", 0.0)
            latency_seconds += data.get("latency_seconds", 0.0)

    return RunMetrics(
        tokens_total=tokens_total,
        cost_usd=round(cost_usd, 4),
        latency_seconds=round(latency_seconds, 2),
        claims_total=claims_total,
        claims_unsupported=claims_unsupported,
        claims_removed=claims_removed,
        claims_overturned=claims_overturned,
        personal_refs_total=personal_refs_total,
        personal_refs_sourced=personal_refs_sourced,
        llm_calls=llm_calls,
        llm_fallbacks=llm_fallbacks,
        retries=retries,
        recovery_decisions=recovery_decisions,
        crustdata_credits=0,
    )


@workflow_span("scholarpilot_run")
def execute_run(run_id: str) -> None:
    """Executes the autonomous ScholarPilot workflow for a run."""
    run = db.get_run(run_id)
    if not run:
        raise ValueError(f"Run {run_id} not found")

    db.add_event(run_id, None, agent="coordinator", type_="run_started", message=f"Run {run_id} started in mode {run['mode']}")

    facts_raw = db.get_facts()
    prefs_dict = db.get_preferences()
    if not facts_raw or not prefs_dict:
        raise ValueError("Cannot execute run without facts and preferences")

    facts = [Fact.model_validate(f) for f in facts_raw]
    prefs = Preferences.model_validate(prefs_dict)
    mode = run["mode"]
    top_n = run.get("top_n", 2)
    live_research = bool(run.get("live_research", False))

    # 1. Scout and Matcher (idempotent if applications exist)
    existing_apps = db.list_applications(run_id)
    if not existing_apps:
        listings = scout.load_listings()
        matcher.match_listings(run_id, listings, facts, prefs, mode=mode, ctx=RunContext(run_id=run_id, mode=mode))
        existing_apps = db.list_applications(run_id)
        matched_apps = [a for a in existing_apps if a.get("status") == "matched"]
        if matched_apps:
            top_match = matched_apps[0]
            top_listing = scout.get_listing(top_match["listing_id"])
            top_name = top_listing.name if top_listing else top_match["listing_id"]
            notify.send_event(
                top_match["id"],
                "matches_found",
                notify.tpl_matches_found(len(matched_apps), top_name, top_match.get("fit_score", 0), top_n),
                run_id,
            )


    # 2. Select top_n matched applications
    matched_rows = [a for a in existing_apps if a.get("status") != "skipped"]
    # Sorting: fit_score DESC, deadline ASC, is_mock tie-break
    def sort_key(app_row: dict[str, Any]):
        fit = app_row.get("fit_score") or 0
        listing = scout.get_listing(app_row["listing_id"])
        deadline = listing.deadline if listing else "9999/99/99"
        is_mock = 0 if (listing and listing.is_mock) else 1
        return (-fit, deadline, is_mock)

    matched_rows.sort(key=sort_key)
    deep_apps = matched_rows[:top_n]

    # 3. Process each selected application through the agent pipeline
    for app_row in deep_apps:
        app_id = app_row["id"]
        listing_id = app_row["listing_id"]
        listing = scout.get_listing(listing_id)
        if not listing:
            continue

        ctx = RunContext(run_id=run_id, app_id=app_id, mode=mode, listing_id=listing_id)

        # Step: research
        dossier: Dossier | None = None
        if mode == "Z":
            dossier = Dossier(listing_id=listing_id, facts=[], degraded=False)
            db.update_application(app_id, dossier=dossier.model_dump())
            db.set_status(app_id, "researched", f"Dossier bypassed in mode Z for {listing.name}", agent="coordinator")
        else:
            dossier = run_step(
                ctx,
                "research",
                lambda: researcher.build_dossier(listing, live=live_research, ctx=ctx),
            )
            if dossier is None:
                continue
            db.update_application(app_id, dossier=dossier.model_dump())
            db.set_status(app_id, "researched", f"Dossier built for {listing.name}", agent="coordinator")
            notify.send_event(
                app_id,
                "researched",
                notify.tpl_researched(listing.name, len(dossier.facts)),
                run_id,
            )

        # Step: edges
        edges: list[Edge] | None = None
        if mode == "Z":
            edges = []
            db.update_application(app_id, edges=[])
            db.set_status(app_id, "edges_selected", f"Edges bypassed in mode Z for {listing.name}", agent="coordinator")
        else:
            def _get_edges() -> list[Edge]:
                e_list, gaps = edge_finder.find_edges(listing, dossier, facts, prefs, ctx)
                for g in gaps:
                    db.add_gap(app_id, g.get("criterion", ""), g.get("question", ""))
                return e_list

            edges = run_step(ctx, "edges", _get_edges)
            if edges is None:
                continue
            db.update_application(app_id, edges=[e.model_dump() for e in edges])
            db.set_status(app_id, "edges_selected", f"Edges selected for {listing.name}", agent="coordinator")
            selected_edges = [e for e in edges if e.selected]
            if selected_edges:
                edge_items = [
                    {
                        "fact_id": e.profile_fact_ids[0] if e.profile_fact_ids else "N/A",
                        "short_fact": e.reason[:30],
                        "reason": e.reason,
                    }
                    for e in selected_edges
                ]
                notify.send_event(app_id, "edges_used", notify.tpl_edges_used(edge_items), run_id)

        # Step: tailor
        sources = tailor.build_sources(listing, facts, dossier, edges, prefs)
        tailored: TailoredOutput | None = None
        if listing.ai_policy in ("restricted", "unknown"):
            tailored = run_step(
                ctx,
                "tailor",
                lambda: tailor.tailor_notes_only(listing, facts, dossier, edges, prefs, ctx),
            )
        else:
            tailored = run_step(
                ctx,
                "tailor",
                lambda: tailor.tailor_full(listing, sources, edges, prefs, ctx),
            )
        if tailored is None:
            continue
        db.update_application(app_id, tailored=tailored.model_dump())
        db.set_status(app_id, "tailored", f"Tailored application for {listing.name}", agent="coordinator")

        # Step: verify
        verify_result: tuple[TailoredOutput, VerificationReport] | None = None
        if mode in ("A", "Z"):
            verify_result = run_step(
                ctx,
                "verify",
                lambda: verifier.verify_mode_a(tailored, sources, ctx),
            )
        else:
            verify_result = run_step(
                ctx,
                "verify",
                lambda: verifier.verify_mode_b(tailored, sources, listing, ctx),
            )
        if verify_result is None:
            continue
        final_tailored, report = verify_result
        db.update_application(
            app_id,
            tailored=final_tailored.model_dump(),
            verification=report.model_dump(),
        )
        db.set_status(app_id, "verified", f"Verified application for {listing.name}", agent="coordinator")
        supported_cnt = sum(1 for c in report.claims if c.verdict == "supported")
        notify.send_event(
            app_id,
            "verified",
            notify.tpl_verified(
                listing.name,
                supported_cnt,
                len(report.removed_claims),
                len(report.overturned_claims),
            ),
            run_id,
        )

        # Step: package (Placeholder for B13: transitions to ready)
        db.set_status(app_id, "ready", f"Package ready for {listing.name}", agent="coordinator")

        # Step: apply (Placeholder for B13)

    # 4. Finalize run and compute metrics
    metrics = compute_metrics(run_id)
    db.finish_run(run_id, "completed", metrics=metrics.model_dump())
    db.add_event(run_id, None, agent="coordinator", type_="run_completed", message=f"Run {run_id} completed successfully")
    notify.retry_unsent()


def start_run_thread(run_id: str) -> threading.Thread:
    """Starts the run execution in a background daemon thread with top-level error handling."""
    def _runner() -> None:
        try:
            execute_run(run_id)
        except Exception as e:
            db.finish_run(run_id, "failed")
            db.add_event(run_id, None, agent="coordinator", type_="run_failed", message=str(e))

    thread = threading.Thread(target=_runner, daemon=True)
    thread.start()
    return thread


def resume_run(run_id: str) -> threading.Thread:
    """Resumes an interrupted or failed run."""
    run = db.get_run(run_id)
    if not run or run["status"] not in ("interrupted", "failed"):
        status_val = run.get("status") if run else "not_found"
        raise ValueError(f"Run {run_id} cannot be resumed from status '{status_val}'")

    conn = db.get_connection()
    try:
        with conn:
            conn.execute("UPDATE runs SET status = 'running', finished_at = NULL WHERE id = ?", (run_id,))
    finally:
        conn.close()

    return start_run_thread(run_id)
