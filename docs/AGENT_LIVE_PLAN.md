# AGENT_LIVE_V1: live ScholarPilot agent and Neatlogs evidence

Authorized by the user's request to implement the previously proposed order.
Use the existing v1 contract, application events, four screens, PostgreSQL,
Redis, worker and fictional portal. No new public endpoints or database fields.

1. Live generation: `backend/app/llm.py::provider_completion(...)` provides the
   existing OpenAI-compatible provider through a once-wrapped SDK client.
   `app/core/llm_gateway.py::call_llm(...)` retains validated usage, retries and
   spending limits. Explicit agent mode never substitutes mock output.
2. Bounded decisions: `app/agents/planner.py::run_application_agent(application,
   scholarship, session, live_research)` chooses research, evidence selection,
   draft-and-verify, and finish from a state-dependent whitelist. Six decisions
   maximum; only reviewed nonsensitive sources; human approval before submission.
3. Evidence: extend `run_edge_finder` to select reviewed source IDs through the
   model and validate references. Research may fetch only the owned fictional
   about page or the existing protected public retrieval path.
4. Observability: workflow context IDs, named prompt chains, wrapped LLM calls,
   tool observations, every verification round and adversarial challenge,
   recovery spans/events/logs, and measured usage. Existing application events
   expose actual decisions and usage in the timeline. Link the dashboard with
   actual trace IDs; distinguish local capture from verified ingestion.
5. Demonstration: opt-in launcher agent mode, authenticated SDK Doctor probe,
   one real synthetic application, actual trace readback, source-backed draft,
   review gate and demo receipt. Record failures honestly. Configure detections
   and inspect Analytics/Investigate where authenticated access permits.

Tests: whitelist rejects premature finish/unknown actions; iteration bound;
source IDs validated; sensitive evidence excluded; checkpoint reuse; provider
failure cannot become success; live SDK call captures actual usage; guardrails
include blocked rounds. Run root pytest, backend quick check and frontend checks.

Trace plan: WORKFLOW scholarpilot_run; AGENT coordinator, researcher, edge_finder,
tailor, verifier; CHAIN llm_planner_v1, llm_edge_v1, llm_tailor_v1,
llm_verifier_judge_v1, llm_challenger_v1, llm_tailor_revise_v1,
recovery_decision; TOOL research/select_evidence/draft_and_verify; GUARDRAIL
verification_round/adversarial_challenge. No fabricated links or metrics.

## AGENT_AUTOPILOT_V1 (authorized 2026/10/12)

Remove the planner's unconditional approval pause for allowed/disclose owned-portal applications in Autopilot. Reuse existing user settings: frontend exposes persisted Autopilot toggle, default on for new users; off selects Review. `planner.finish_application(...)` validates persisted draft/verification, checks current mode and queues one submit job. Settings writes an owner-scoped Redis pause marker; browser checks it immediately before automatic Submit. Manual approval remains available in Review. No new endpoints, public fields or dependencies.

Tests: autopilot queues once without approval; Review pauses; unsafe portal stays manual; unchecked draft cannot submit; runtime owner pause blocks automatic submit without blocking explicit Review approval. Existing kill switch, CAPTCHA and real-portal restrictions remain. Run root suite, backend quick check, frontend types/lint. Trace finish TOOL records actual queued/review outcome.
