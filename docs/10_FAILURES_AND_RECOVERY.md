# 10_FAILURES_AND_RECOVERY.md

The recovery rules, the failure flags, the detections to create in neatlogs, and the procedure to record failure evidence. The long catalog of 83 possible failures is in `23_FAILURE_PLAYBOOK_REFERENCE.md`.

## 1. Principles

1. One failure never stops the run. The Coordinator catches per application.
2. Every recovery is a recorded decision: a `recovery_decision` span, an event of the same type, and a log line (`04_ARCHITECTURE.md` section 8, helper `coordinator.record_recovery`).
3. Deterministic rules choose the recovery. The reason is one honest sentence that names the evidence.
4. Never retry against a blocker (CAPTCHA, login wall). Hand off.
5. Never mark `submitted` without a confirmation.
6. Injected failures are labeled `failure_injected` everywhere they appear.

## 2. Recovery matrix (deterministic rules)

Format: trigger, options, chosen rule, reason template, expected outcome.

1. `llm_429` (rate limit or quota):
   1. Options: `retry`, `fallback_model`.
   2. Rule: retry with backoff; on the second consecutive failure choose `fallback_model`.
   3. Reason: `Rate limited {n} times in a row on {model}, so switching to the backup model.`
   4. Outcome: `success` when the fallback call works, `failed` if both fail (step fails, application fails, run continues).
2. `llm_timeout` (timeout or provider 5xx): same options and rule as `llm_429`. Reason: `Provider timed out {n} times, so switching to the backup model.`
3. `model_not_found` (404 for the model id): options `fallback_model`. Rule: immediate switch, no retries. Reason: `The primary model id was rejected as not found, so using the backup model.` Also add an event telling the human to fix `LLM_PRIMARY_MODEL`.
4. `bad_json`: options `repair`, `regenerate`, `fallback_model`. Rule: repair first, regenerate at temperature 0 second, fail the step third. (Not a span of kind recovery for each, the `json_repair` event plus attribute `json_repaired` is enough.) Reason for the regenerate decision: `Repair did not produce valid JSON, so regenerating at temperature 0.`
5. `research_unreachable`: options `use_cache`, `degrade_dossier`. Rule: `use_cache` when a cache file exists, else `degrade_dossier`. Reason: `Live source failed and a cached dossier with source URLs exists.` or `No live source and no cache, so using only the listing's own criteria and making no school specific claims.`
6. `claim_unsupported` (verifier): options `revise`, `remove`. Rule: `revise` for rounds 1 and 2, `remove` after. Reason: `{n} claims lack source support, sending them back to the Tailor (round {r}).` or `Still unsupported after 2 revisions, removing the sentence.`
7. `claim_overturned` (challenger): same options and rules as `claim_unsupported`, with one revision.
8. `portal_500`: options `retry`, `email_fallback`, `prepare_package`. Rule: retry 3 times, then `email_fallback` when `listing.email` is not empty, else `prepare_package`. Reason: `Portal returned an error 3 times, so switching to {chosen}.`
9. `captcha_wall` (or any blocker): options `retry`, `handoff`. Rule: `handoff` always. Reason: `A CAPTCHA can only be solved by the user, so the agent stops and hands off.` Outcome: `handed_off`.
10. `smtp_failure`: options `retry`, `prepare_package`. Rule: `prepare_package`. Reason: `The email could not be sent, so the package is prepared for manual submission.`
11. `confirmation_missing` (submit returned success but no confirmation after 3 polls): options `retry_poll`, `mark_unconfirmed`. Rule: `mark_unconfirmed`. Reason: `No confirmation was seen, so the application is marked unconfirmed and the user is told.`
12. `telegram_failure`: no decision span. Log an event, keep the notification row unsent, retry at the end of the run.
13. `thread_crash` (unexpected exception in the run thread): not a decision. The thread entry point records a `failed` run with the error text. The user can resume (`POST /api/runs/{id}/resume`).

## 3. Failure flags (implementation)

Flags live in the `failure_flags` table (`name`, `enabled`, `remaining`). Seed names: `llm_429`, `bad_json`, `portal_500`, `captcha_wall`, `research_down`, `smtp_fail`, `injection_page`.

Behavior of each flag and the exact hook point:
1. `llm_429` (counted, default count 2): in `call_llm`, before calling the PRIMARY client, `db.consume_flag("llm_429")` true means: record `failure_injected`, treat it as a rate limit error without calling the provider. Because the count is 2 the retry and then the fallback happen naturally.
2. `bad_json` (counted, default count 1): in `call_llm` after a successful response, truncate the text to its first half, record `failure_injected`, continue into the repair path.
3. `portal_500` (counted, default count 3): in the portal `POST /portal/api/submit` handler, `consume_flag("portal_500")` true returns HTTP 500 and records `failure_injected` with agent `portal`.
4. `captcha_wall` (uncounted, stays on until switched off): the apply and draft pages show the challenge, and submit requires the right answer. Record `failure_injected` once per application when the Applier detects the blocker.
5. `research_down` (uncounted): `researcher.fetch_live` raises `ResearchError("simulated")`. The Researcher tries live when this flag is on (see `07_AGENTS_SPEC.md` section 5).
6. `smtp_fail` (counted, default count 1): `notify.send_email` raises `SmtpError("simulated failure")`.
7. `injection_page` (uncounted): the portal about page appends the injection paragraph. The Researcher (live path) must drop that line and record `injection_dropped`.

How to use: `POST /api/failure_flags` with `{"flags": {"llm_429": true}, "counts": {"llm_429": 2}}`. Always clear flags after the evidence run. Tests never rely on live flags (they use the db functions directly).

## 4. Procedure to record failure evidence (B22)

For each flag do exactly this and record results in `17_EVIDENCE_CHECKLIST.md` section 3:
1. Make sure all flags are off. Note the time.
2. Enable ONE flag with its count. Start a run (mode B, top_n 2, tags `recovery,<flag>` via `run_pipeline.py`, so the process tags the traces).
3. Expected:
   1. `llm_429`: events `failure_injected`, two `retry` events, one `recovery_decision` (trigger `llm_429`, chosen `fallback_model`), the run completes. neatlogs shows the failed attempts and the fallback call as siblings under one `llm_` span, with `fallback_used` true.
   2. `bad_json`: events `failure_injected` and `json_repair`, the step succeeds.
   3. `portal_500`: 3 `retry` events, a `recovery_decision` (chosen `email_fallback` or `prepare_package`), the application ends `submitted` by email or `prepared`.
   4. `captcha_wall`: `blocker_detected`, a `recovery_decision` (chosen `handoff`), Telegram message, status `awaiting_user`. Then solve the challenge on the portal page, press Done, status `submitted`.
   5. `research_down`: `failure_injected`, `research_used_cache`, a `recovery_decision` (chosen `use_cache`).
   6. `smtp_fail`: `failure_injected`, a `recovery_decision` (chosen `prepare_package`), status `prepared`.
   7. `injection_page`: events `injection_detected`, span attribute `injection_dropped` above 0, the dossier contains no text from the injected line, and no acceptance claim appears anywhere.
4. Screenshot: the neatlogs trace (span tree with the decision span open showing its reason), the Application Status timeline, and the Telegram message when relevant.
5. Switch the flag off. Note anything that did not behave as expected and fix it.

## 5. Stretch: LLM chosen recovery with a whitelist

Only after everything else works. On a failure, an LLM call `recovery_v1` receives the trigger and the allowed options and returns `{"chosen": "...", "reason": "..."}`. Code accepts the choice only if it is on the whitelist for that trigger. Otherwise it uses the deterministic rule and logs `recovery choice rejected`. Never let the model choose outside the list, and never offer an option that bypasses a CAPTCHA.

Whitelists: `llm_429`: retry, fallback_model. `bad_json`: repair, regenerate, fallback_model. `portal_500`: retry, email_fallback, prepare_package. `captcha_wall`: handoff only. `research_unreachable`: use_cache, degrade_dossier.
Call it a rule based decision in the demo unless the LLM really chose.

## 6. neatlogs detections to create (15 rules)

Create these in the dashboard after the first real trace exists. Scope to the relevant span names if the rule editor allows it. Tune thresholds after run B. Attribute names are the plain names from `09_NEATLOGS_SPEC.md` section 5 (add the `neatlogs.` prefix if plain names are not usable, see the VERIFY there).

Condition rules:
1. D1 high cost: cost per run above 3 times the run B average.
2. D2 slow LLM call: latency above 20000 milliseconds on an LLM span.
3. D3 context bloat: total tokens above 8000 on one LLM span.
4. D4 retry storm: `attempt` greater than 2.
5. D5 fallback used: `fallback_used` equals true.
6. D6 guardrail blocked: `neatlogs.guardrail.passed` equals false.
7. D7 unsupported in final: `claims_unsupported` greater than 0 on the last verification round.
8. D8 loop suspicion: tool call count above 10 in one application.

Regex rules:
9. D9 overreach words in Tailor output: `president|founder|director|years of experience|award winning|led a team of`.
10. D10 provider errors in responses: `429|RESOURCE_EXHAUSTED|no longer available|NOT_FOUND|safety|blocked|I cannot`.
11. D11 prompt injection in fetched pages (Researcher input): `ignore previous|disregard|system prompt|you are now|do not tell`.
12. D12 portal blockers in portal responses: `captcha|login|sign in|forbidden|503|500`.

Classifier rules:
13. D13 sensitive leak: output mentions health, religion, disability or family income (scope: Tailor and Edge Finder spans).
14. D14 generic essay: essay text with no specific evidence from the applicant.

PII detection:
15. D15 PII flow: enable it. Expect hits for the synthetic persona (harmless). For real users it shows exposure and helps confirm third party personal details do not reach prompts.

Evidence: a screenshot of the detections list and the traces list with badges on real runs.

## 7. Investigate prompts (Neat AI)

Use Fast mode for simple questions and Pro mode for broad ones.
1. "Start an investigation on the last 20 traces tagged run_A and tell me the most common cause of unsupported claims."
2. "Which agent spends the most tokens, and which prompt in it is the longest?"
3. "Find traces where fallback_used is true and compare output quality to non fallback runs."
4. "Show runs where portal_submit failed and what the agent did next."
5. "Find traces where the verification passed but the output contains words like president or years of experience."
6. "Why are there so many D10 detections today?"
7. "List the slowest 5 spans and what they were waiting on."
8. "Did any prompt contain sensitive terms such as health or religion?"
9. "Which Researcher inputs contained instruction like text from a web page?"
10. "Summarize what changed between run B and run C and whether it is a real improvement."

## 8. The 10 minute triage routine (after every evidence or test run)

1. Open the traces list filtered by the run tag. Scan detection badges.
2. Open Analytics: cost and latency by agent and tool, errors, detection trend.
3. Open the slowest or most expensive trace. Read the timeline for retry stacks and idle gaps.
4. Open traces with D6, D7, D9 or D13 badges. Read span detail. Vote thumbs down on bad outputs.
5. Ask Investigate one question from section 7.
6. Comment on the span with the finding and tag the owner.
7. Add the finding to `docs/evidence/improvement_log.md`.
8. Fix through Antigravity (neatlogs MCP or the CLI to read the trace), commit, run again.

## 9. Pre demo failure rehearsal checklist

1. [ ] All flags off before recording.
2. [ ] `captcha_wall` rehearsed end to end twice (it appears in the video).
3. [ ] A backup recording of the full runtime exists.
4. [ ] The LLM fallback key works (test with `llm_429`).
5. [ ] The primary model id is valid today (the Gemini 2.5 Flash shutdown is October 16, 2026).
6. [ ] Telegram delivers to your phone and the Done callback works.
