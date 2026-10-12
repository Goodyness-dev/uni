# ScholarPilot live agent demo

Start the configured workstation with:

```powershell
backend/.venv/Scripts/python.exe scripts/local_demo.py start --agent
```

This uses the real PostgreSQL/Redis services and fictional portal described in
the README. Gemini and Neatlogs keys come from ignored local configuration.
The default demo model is `gemini-3.5-flash-lite`, with
`gemini-3-flash-preview` as backup. `AGENT_MODEL` in the ignored root `.env`
can override the primary, but it must have an explicit pricing entry.
These models were checked with completion requests; listing a model alone
does not prove it can answer. Redis reserves and settles model budgets.

Run the repository's reviewed fictional persona from the existing frontend.
The agent chooses from a state-dependent tool whitelist, records observations,
prioritizes selected source IDs, and drafts with independent judge and
Challenger calls. Unsupported sentences trigger up to two revisions, then
removal. Six coordinator decisions maximum, including across job retries.
It always stops at human review. Approval permits only the owned demo portal.

Full prompt capture is limited to the fictional demo identity; ordinary agent
mode defaults to content capture disabled. Source alignment is not document
authenticity, and passing two model judges is not a guarantee of correctness.

## Make Neatlogs visible

The application page shows a View Neatlogs trace link, actual trace ID, measured model
usage, tool decisions, observations, verification rounds and recovery reasons.
The application links to `/traces/{actual_trace_id}` after that dashboard route
was verified through the authenticated browser. Select the correct project if
the dashboard asks for project context. Inspect the recorded span tree. Workflow name remains
`scholarpilot`; worker runs carry the `worker` tag.

Six project detections were created through authenticated MCP:
blocked verification, large model context, wording requiring review, prompt
injection text, observed recovery and model spend review. Creation responses
are in `evidence/neatlogs_detection_setup.json`. Flags identify review targets;
they do not prove a factual error. Existing project rules remain intact.

Use the existing MCP integration to read exact trace context and Analytics:

```powershell
backend/.venv/Scripts/python.exe scripts/neatlogs_evidence.py get_trace_context --trace-id ACTUAL_TRACE_ID --output storage/local_runtime/trace_readback.json
```

The helper reads configured credentials without putting them in command lines.
Default full-context readback works on this project; selective paging currently
returns a server capability error, so do not claim selective paging is available.
Local SDK Doctor passed. The authenticated Doctor probe timed out during
server-side processing; real application trace readback was separately verified.

## The real improvement example

Trace `fd911277e30ccad4cddcd3221bb0eae3` finalized with 114 spans, 12 LLM calls,
43,253 tokens and blocked-verification/recovery detections. Its first round
rejected two sentences, but manual review found unsupported causal wording
that both model judges accepted. The application was held at human review.
The source said students entered a science fair later; the draft said teaching
resulted in their entry. Aspirations also risked becoming accomplishments.

The fix adds deterministic checks for unsupported causal bridges and aspiration
conversion, tightens both judge prompts, and corrects possessive-name matching
that had incorrectly rejected literal source text. Regression tests cover the
actual failure pattern. A subsequent real run is recorded separately; the first
run is retained rather than presented as a clean success.

Gemini-compatible token totals may include thinking tokens absent from the
completion count. The transport normalizes billed output from the provider's
total minus input before the wrapped client reports usage to Neatlogs. Model
cost is an estimate using published text rates, not an invoice:
[Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing).

For the video: show the real Neatlogs trace near the start, the unsupported
claim and source, the code change and regression, then the new run and demo
receipt. Open Analytics for measured cost/latency/tools. Session Replay is
experimental; inspect it on the actual trace if available. Investigate, Evals,
comments and prompt promotion require dashboard access and should only be
claimed once exercised. No simulated trace is used as live application proof.

## Verified outcome and dashboard limits

The improved application `0a10f49a-da06-4bed-9127-0c23ba3c2285` was reviewed against its source facts and submitted to the owned portal. Authoritative receipt: **DEMO1584**. Actual finalized trace `7aeb442a172e5c5179639b86fa39f867` reports 112 spans, 11 model calls, 33,537 tokens, 116.568 seconds and estimated cost $0.0246933. Its Replay player was opened, played and paused on real tool/model steps. Public evidence is in `evidence/agent_after_source_review_20261012.json` and `evidence/agent_local_e2e_20261012.json`.

Investigate fetched both real traces and queried evidence, then entered repeated pagination. It was stopped; a bounded summary request and one retry both lost connection. No completed investigation answer is claimed. Evals and external coding-agent dispatch were not configured. Current MCP context readback returns 50 spans; selective pagination fails with a project capability error. These limitations belong in the demo disclosure.

The preceding run cost $0.0373959 for 43,253 tokens; the new run cost $0.0246933 for 33,537 tokens. Inputs and model timing varied, so this single pair does not establish a general savings or quality rate. The earlier causal error remains visible and its application was never submitted.

## Autopilot follow-up

Autopilot no longer pauses every application for approval. An allowed/disclose application with a persisted nonempty source-checked draft queues the actual submitter automatically. The profile checkbox uses existing `/v1/settings` endpoints; off selects Review and writes an owner-scoped Redis pause marker. The submitter rechecks mode; the browser rechecks that marker immediately before automatic Submit. Accepted submissions cannot be undone, and there is an unavoidable interval between the final check and the portal accepting its request. Existing Review applications keep their original review requirement.

This does not enable real scholarship submissions or bypass login/CAPTCHA; both remain prohibited. A successful agent can operate entirely in an owned sandbox. Source review at onboarding remains separate from per-application approval.

Autopilot's fresh live run obtained **DEMO2985** without an approval endpoint or approval event. Finalized trace `3720e970f1789d3418667a9194a024af` reports 99 spans, 12 LLM calls, 17,550 tokens and 54.834 seconds. Neatlogs marks this trace `error` with four span errors and an Execution Failed detection, although recovery completed and the portal receipt was verified. This is not a clean provider run; retained evidence includes those errors.
