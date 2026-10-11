# NEATLOGS_DEEP_USE.md

How to use neatlogs far more deeply than "we traced our calls". Read it with `NEATLOGS.md` (basics) and `TOOLS_RESEARCH.md` section 1 (facts from the docs).

## 1. Why this matters

1. Tool use is 25 percent of the score, and the neatlogs founders are judges. They score how EFFECTIVELY we used neatlogs to build and improve the agent, not whether the SDK is installed.
2. The strongest entries will show a loop: trace, find the cause, fix, trace again, compare. Other teams already show recovery decisions traced with reasons, self audits, and agents that read traces to fix code.
3. Deep use also gives us real evidence for the agent score (30 percent) and the demo score (20 percent).

## 2. Usage levels (where we are and where we go)

1. Level 1, basic tracing: every LLM and tool call traced. (This is where the first plan stopped.)
2. Level 2, meaningful traces: GUARDRAIL spans for verification, RETRIEVER spans, tags, custom attributes, structured logs, prompt templates, sessions.
3. Level 3, decisions visible: every retry, fallback and recovery decision is a span with its trigger, options, choice and reason.
4. Level 4, the improvement loop: Antigravity reads our traces through the neatlogs MCP server and fixes the code, twice, with before and after numbers.
5. Level 5, product integration and evaluation: the app links to its own traces, runs a small evaluation set, and uses neatlogs Detections, Analytics and Comments.

Target: Level 4 for sure, Level 5 where time allows.

## 3. The upgrades

### U1. Recovery decision spans (Level 3, about 40 minutes, Memeshi)

Every time the agent recovers from something, record WHY in a span. Add `recovery_decision()` to `tracing.py` as a context manager over `neatlogs.trace("recovery_decision", kind="CHAIN")`.

Attributes to set on it:
1. `recovery.trigger`: what happened (llm_429, bad_json, portal_500, captcha_wall, research_unreachable, claim_unsupported).
2. `recovery.options`: the options considered, as one string (for example retry, fallback_model, handoff, prepare_package).
3. `recovery.chosen`: the option taken.
4. `recovery.reason`: one sentence of reasoning (for example "second 429 in a row, so switching to the backup model").
5. `recovery.attempt` and `recovery.outcome` (success, failed, handed_off), set after it runs.

Also write a structured log line with `neatlogs.log` (needs `capture_logs` on in init). Persist the same decision as an `events` row of type `recovery_decision` so the app timeline shows it. The Coordinator is the only place that creates these decisions.

Default design: deterministic rules choose the recovery (safe and testable). Stretch version (U11 below): an LLM picks from a whitelist.

Evidence: one screenshot per failure type showing the decision span with its reason.

### U2. Disprove your own claims (Level 2, about 60 minutes, Memeshi)

Add an adversarial challenge after the Verifier marks claims supported. A separate LLM call (`challenger_v1`, see `AGENT_PROMPTS.md`) tries to find how each supported claim could mislead a committee: stretching a title, implying a longer duration, claiming impact the fact does not state, or making a school claim stronger than the dossier snippet. Claims it can defend stay. Claims it overturns are removed or rewritten by the Tailor (round limit still 2) and listed as OVERTURNED in the report.

In neatlogs:
1. Two GUARDRAIL spans per round: `verification_round` and `adversarial_challenge`, each with `neatlogs.guardrail.passed`, input and output reason.
2. Span attributes: `claims_checked`, `claims_overturned`.
3. The run metrics gain `claims_overturned`.

In the product: the Application Status screen shows an "Overturned by self challenge" list next to removed claims. This is a strong demo moment and matches the story other teams tell.

### U3. The improvement loop through the neatlogs MCP server (Level 4, Memeshi)

Do the loop TWICE and keep a log.

Loop 1 (Sunday morning):
1. Run A, tagged `run_A`.
2. In the Antigravity CLI, with the neatlogs MCP connected, ask it to search traces for the latest `run_A`, read the trace context and list Verifier GUARDRAIL spans that reported unsupported claims.
3. It proposes the fix (enforcement loop). You approve and commit. The Entire checkpoint records the reasoning.
4. Run B, tagged `run_B`. Compare.

Loop 2 (Sunday evening, after the failure injections):
1. Ask the agent to read the trace of the slowest or most expensive application and the recovery traces.
2. Pick ONE real improvement it finds (for example fewer tokens in the Verifier judge prompt, batching claims, or skipping retries on non retryable errors).
3. Apply it, tag the next run `run_C`, and compare cost and latency against run B.

Keep `docs/evidence/improvement_log.md` with one entry per loop: trace link, finding, commit hash and Entire checkpoint, before and after numbers. This single file is the best proof that we used neatlogs to improve the agent.

Setup facts and the tools are in `NEATLOGS.md` section 6. If the MCP connection to Antigravity does not work, do the same loop manually (read the trace in the dashboard, paste the findings into the prompt) and say so honestly.

### U4. Detections and Analytics (Level 5, about 30 minutes)

1. After run A, open Detections and note what neatlogs flags on our traces. Screenshot it. If it flags something real, fix it and record it in the improvement log.
2. Use Analytics for cost, latency and errors by agent and tool. Screenshot the per agent cost and the slowest tool. These numbers feed `CFO_PLAN.md` and the demo.
3. Use Session Replay on the CAPTCHA handoff run to show the pause and resume.

### U5. Prompt versioning (Level 2, about 30 minutes)

1. Every LLM span uses `SystemPromptTemplate` and `UserPromptTemplate` so the template and the runtime variables are visible. Prompt id and version go in the span name and attributes.
2. Stretch: store the Tailor prompt in neatlogs Experiments under Prompts, fetch it by label (production) at runtime, and publish a v2 for run C. VERIFY the fetch API on the Experiments page of the docs. If it is unclear, keep prompts local and still show versions through the templates.

### U6. Sessions and users (Level 2, about 20 minutes)

1. Session Replay is experimental and today one trace equals one session, so group a run by making the run one WORKFLOW trace and by using tags and attributes, not multi trace sessions. Session Replay still works well for replaying one run. VERIFY the exact session API on the Sessions page of the docs. Result: ______
2. Set a user id for the synthetic persona (a fake id) so the dashboard can filter by user. Never use a real person's id.

### U7. Structured logs at decisions (Level 2, about 20 minutes)

Use `neatlogs.log` with placeholders at the moments that matter: edge selected (with fact id and reason), claim removed (with reason), channel chosen, blocker found, handoff sent, confirmation seen, recovery chosen. These logs appear in the span view and make traces read like a story.

### U8. The product links to its own traces (Level 5, about 45 minutes, Memeshi and Ayo)

1. Add a `trace_url` field to each application (and to the run) in the API. Use the neatlogs dashboard URL for that trace if the SDK can return the trace id (VERIFY on the Python SDK page). If not, build a dashboard link filtered by tag and application id, and say so.
2. Ayo adds a View trace button on Application Status and on the run header, and the Run metrics strip on Matches (tokens, cost, time, claims checked, removed, overturned) fed by the metrics.
3. Contract change: add `trace_url` to the Application and Run shapes in `ARCHITECTURE.md` (a `contract:` commit).

### U9. Small evaluation set and regression gate (Level 5, about 45 minutes)

1. A script runs the persona against all eligible listings in mode B three times with tags `eval` and `eval_v1`.
2. It prints a table (claims total, unsupported final, overturned, cost, latency, recovery decisions) and exits with an error if any final output has an unsupported claim.
3. Run it again after the loop 2 improvement with `eval_v2` and compare in neatlogs.
4. This is our regression gate, and the same idea scales in `PRODUCTION_UPGRADE.md` section 11.

### U10. Comments on traces (Level 5, about 10 minutes)

Memeshi and Ayo leave comments on the important traces in the dashboard (the run A finding, the recovery traces, the loop fixes), describing what we learned. Screenshot one thread. It shows team use.

### U11. Stretch: LLM chosen recovery with a whitelist

Only if everything else is done. When a failure happens, an LLM call (`recovery_v1`) receives the trigger and the allowed options and returns `{"chosen": "...", "reason": "..."}`. Code accepts the choice only if it is on the whitelist for that trigger, otherwise it uses the deterministic rule and logs that the choice was rejected. Never let the model pick anything outside the whitelist, and never let it choose to bypass a CAPTCHA (that option never exists).

Whitelists:
1. llm_429: retry, fallback_model.
2. bad_json: repair, regenerate, fallback_model.
3. portal_500: retry, email_fallback, prepare_package.
4. captcha_wall: handoff only.
5. research_unreachable: use_cache, degrade_dossier.

### U12. Stretch: trace our own coding sessions

The neatlogs MCP server has a tool for pushing a trace from the coding agent. If it works with Antigravity, push the key build sessions so neatlogs shows how the agent itself was built. VERIFY first. Do not spend more than 20 minutes.

## 4. Updated neatlogs demo segment (about 40 seconds)

Take 10 seconds from the architecture slide and the closing line.

1. 0 to 8 seconds, architecture and runtime: one trace with WORKFLOW, AGENT, RETRIEVER, TOOL, GUARDRAIL and LLM spans. Point at the GUARDRAIL showing Passed.
2. 8 to 18 seconds, reasoning: run A shows {N_A} unsupported claims. Show the MCP loop: "Antigravity read this trace through the neatlogs MCP server and proposed the fix."
3. 18 to 28 seconds, result: run A versus run B numbers, then the second loop (cost down {Y} percent).
4. 28 to 40 seconds, recovery: the recovery decision span: "rate limit twice, so switched to the backup model" and the CAPTCHA handoff with its reason.

Implementation (one screen): the wrap call, one span decorator, and the recovery decision helper.

## 5. New tasks (also copied into `TASKS.md`)

1. N01. [ ] `recovery_decision()` helper and events (M, 40 min, depends on B04, B14).
2. N02. [ ] Prompt templates and `neatlogs.log` calls at decision points (M, 30 min, depends on B04).
3. N03. [ ] Challenger prompt, adversarial GUARDRAIL span, overturned list in the report (M, 60 min, depends on B16).
4. N04. [ ] Neatlogs MCP connected to Antigravity and tested (M, 20 min, depends on B02).
5. N05. [ ] Improvement loop 1 and the improvement log (M, 30 min, depends on B15, B17).
6. N06. [ ] Sessions, user id and tags wired in `run_pipeline.py` (M, 20 min, depends on B14).
7. N07. [ ] `trace_url` in the contract, plus View trace button and Run metrics strip (M 20 min, A 40 min, depends on N06).
8. N08. [ ] Detections and Analytics review with screenshots (M, 30 min, depends on B17).
9. N09. [ ] Evaluation script and regression gate (M, 45 min, depends on B21).
10. N10. [ ] Improvement loop 2 and run C comparison (M, 45 min, depends on B22).
11. N11. [ ] Comments on key traces (B, 10 min).
12. N12. [ ] Stretch: LLM chosen recovery with whitelist (M, 60 min).
13. N13. [ ] Stretch: push coding sessions as traces (M, 20 min).

Cut order for these if time is short: N13, N12, N09, N11, N08. Never cut N01, N03, N04, N05.

## 6. New evidence to collect

1. [ ] Recovery decision span screenshots with reasons (one per failure type).
2. [ ] Challenger result: a real overturned claim, with the original text and the reason.
3. [ ] `docs/evidence/improvement_log.md` with 2 loops, each with trace link, commit hash, Entire checkpoint and numbers.
4. [ ] Screenshot of the neatlogs MCP session in Antigravity reading a trace.
5. [ ] Detections and Analytics screenshots.
6. [ ] Session Replay of the handoff.
7. [ ] Evaluation table for `eval_v1` and `eval_v2`.
8. [ ] A comment thread screenshot.
9. [ ] The View trace button working in the app.

## 7. Honesty rules

1. Every trace and number shown must come from real runs. No staged or edited screenshots.
2. Injected failures stay labeled as injected.
3. If the MCP connection or a feature does not work, say so and show the manual version.
4. Do not claim the LLM chose a recovery unless it did. Deterministic decisions are fine, call them rules.
