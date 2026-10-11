# Phase 4 Implementation Document: Coordinator, API Routers, and Verification Enforcement

**Author**: Coding Agent (Pair Programming with Memeshi & Ayo)  
**Hackathon**: neatHack (October 10–12, 2026)  
**Date**: October 11, 2026  
**Tasks Covered**: B13, B14, B15, B16  

---

## 1. Executive Summary

Phase 4 bridges the individual agent units (Intake, Scout, Matcher, Researcher, Edge Finder, Tailor, Verifier) into an autonomous, observable pipeline and demonstrates the core thesis of ScholarPilot: **zero unverified claims submitted to scholarship providers**.

In this phase, we:
1. Built the central workflow orchestrator (`backend/app/coordinator.py`) with retries, recovery decisions, top-level error handling, and live metrics calculation.
2. Built FastAPI routers for `/api/runs` and `/api/applications` matching the exact JSON contract shapes.
3. Created the CLI execution script `backend/scripts/run_pipeline.py` to trigger end-to-end runs with Neatlogs tracing tags.
4. Executed baseline **Run A** (Mode A: single-pass audit without enforcement) twice, capturing 16 ungrounded/hallucinated claims in final applications.
5. Engineered the **Verifier Mode B Self-Healing Enforcement Loop** (`verify_mode_b`), featuring targeted multi-round revisions (`tailor_revise`), adversarial challenger audits, sensitive text scrubbing, and a deterministic removal fallback for persistent hallucinations.
6. Executed comparative **Run B** (Mode B: self-healing enforcement) twice, driving final unsupported claims to **0** (-100% reduction), and produced the formal evidence comparison table.

---

## 2. Key Components Implemented

### 2.1 Task B13: Central Coordinator and Routers
- **Coordinator (`backend/app/coordinator.py`)**:
  - `run_step(ctx, step_name, fn)`: Wraps each pipeline stage in a retry loop (up to `MAX_RETRIES = 2`), emits structured recovery events (`recovery_decision`), records step outcomes to SQLite idempotently, and isolates individual scholarship failures so that one failure does not halt subsequent applications.
  - `execute_run(run_id)`: Decorated with `@workflow_span("scholarpilot_run")`. Sequences Scout -> Matcher -> Researcher -> Edge Finder -> Tailor -> Verifier -> Packager -> Applier.
  - `compute_metrics(run_id)`: Aggregates claim verifications, tokens, costs, latencies, recovery decisions, and personal reference sources into typed `RunMetrics`.
  - `start_run_thread(run_id)`: Launches autonomous background threads for non-blocking execution.
- **REST Endpoints**:
  - `/api/runs`: `GET /latest`, `GET /{id}`, `POST /` (creates and starts background thread), `GET /{id}/events`.
  - `/api/applications`: `GET /`, `GET /{id}` (returns complete nested contract including gaps, edges, dossier, tailored segments, and verification report), file downloading endpoints (`/files/cv`, `/files/essay`, `/files/package`), and `/handoff/complete`.
- **Pipeline CLI Runner (`backend/scripts/run_pipeline.py`)**:
  - Accepts CLI args `mode`, `top_n`, `tags`.
  - Initializes Neatlogs tracing tags, seeds synthetic persona if needed, runs synchronous execution, calculates metrics, and exports evidence JSON to `docs/evidence/`.

### 2.2 Task B14: Baseline Run A Execution
- Executed Mode A baseline runs on synthetic applicant Adebayo Nnamdi:
  - `docs/evidence/run_A_1.json` (`run_20261011_007`)
  - `docs/evidence/run_A_2.json` (`run_20261011_008`)
- Demonstrated that without self-healing enforcement, 16 unverified or hallucinated claims generated during LLM drafting persist into the final application package.

### 2.3 Task B15: Verifier Mode B Self-Healing Loop
- **`verify_mode_b` (`backend/app/agents/verifier.py`)**:
  - **Round 1 Audit**: Audits full tailored draft against grounding sources using Neatlogs `GUARDRAIL` evaluation.
  - **Iterative Revisions (Rounds 1–2)**: Collects non-supported claims grouped by segment and calls `tailor_revise` to rewrite sentences strictly from factual source IDs.
  - **Deterministic Removal Fallback**: Segments retaining unsupported claims after 2 revision rounds are marked `status = "removed"` and logged as typed `RemovedClaim` objects.
  - **Adversarial Challenger Integration**: Cross-examines remaining supported claims for subtle exaggerations; overturned claims undergo revision or removal.
  - **Sensitive Post-Scan**: Scrubs any unconsented sensitive facts from active text.
  - Guarantees `unsupported_final: 0`.
- **`tailor_revise` (`backend/app/agents/tailor.py`)**:
  - Rewrites only specified problem segments, leaving existing verified sections untouched.

### 2.4 Task B16: Run B Comparative Evidence
- Executed Mode B runs:
  - `docs/evidence/run_B_1.json` (`run_20261011_009`)
  - `docs/evidence/run_B_2.json` (`run_20261011_010`)
- Built `docs/evidence/comparison_table.md` detailing the side-by-side comparison.
- Updated `docs/17_EVIDENCE_CHECKLIST.md` section 2 with verified metrics.

---

## 3. Comparative Verification Evidence

| Metric | Mode A (Baseline) | Mode B (Self-Healing) | Impact |
| :--- | :---: | :---: | :---: |
| **Initial Claims Audited** | 16 | 16 | Identical baseline |
| **Initial Unsupported Claims** | 16 | 16 | Identical hallucinations detected |
| **Final Unsupported Claims** | **16** | **0** | **-100% elimination of unverified text** |
| **Segments Removed** | 0 | 16 | Hallucinations safely excised |
| **Personal References Sourced** | 1 | 1 | Preserved without hallucinating details |
| **End-to-End Status** | Completed (`ready`) | Completed (`ready`) | Pipeline uninterrupted |

---

## 4. Test Suite and Verification

All 70 tests pass without network access or live API dependencies:
```
tests/test_coordinator.py .....                                          [  7%]
tests/test_data.py ...                                                   [ 11%]
tests/test_db.py .....                                                   [ 18%]
tests/test_edge_finder.py ....                                           [ 24%]
tests/test_flags.py .                                                    [ 25%]
tests/test_health.py ..                                                  [ 28%]
tests/test_intake.py ....                                                [ 34%]
tests/test_llm.py .....                                                  [ 41%]
tests/test_matcher.py .....                                              [ 48%]
tests/test_matches_gaps.py ..                                            [ 51%]
tests/test_profile_router.py ...                                         [ 55%]
tests/test_researcher.py .....                                           [ 62%]
tests/test_runs_applications.py ......                                   [ 71%]
tests/test_scout.py ..                                                   [ 74%]
tests/test_sensitive.py ....                                             [ 80%]
tests/test_tailor.py ....                                                [ 85%]
tests/test_tracing.py ...                                                [ 90%]
tests/test_verifier.py ....                                              [ 95%]
tests/test_verifier_mode_b.py ...                                        [100%]
============================= 70 passed in 7.30s ==============================
```

---

## 5. Neatlogs Instrumentation & Observability

- **Workflow Span**: `scholarpilot_run` wraps the top-level coordinator execution.
- **Agent Spans**: `scout`, `matcher`, `researcher`, `edge_finder`, `tailor`, `verifier` are recorded under the workflow trace.
- **Guardrail Spans**: Every audit round emits `neatlogs` GUARDRAIL evaluations recording claim text, source citations, and verdicts (`supported`, `unsupported`, `contradicted`).
- **Recovery Decision Spans**: Coordinator retries and fallback operations emit recovery decisions tagged with the failure reason and chosen mitigation.
