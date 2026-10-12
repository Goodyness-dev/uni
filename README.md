# ScholarPilot

ScholarPilot is a scholarship application assistant built for neatHack, October 10–12, 2026. Memeshi works on backend/agents and Ayo on the frontend.

**Current status: development prototype with production repair work in progress. It is not ready for real applicant data or real scholarship submissions.**

## The problem we are working on

ScholarPilot is built around a practical problem for students in Nigeria: finding suitable scholarships and preparing multiple applications takes research, repeated writing and careful attention to deadlines. Speed and application volume matter, but a faster application is harmful if it invents grades, accomplishments or eligibility. Our goal is to help students reuse their actual evidence, research opportunities and prepare grounded applications with a visible trail of decisions.

The hackathon demonstrates this with **fictional applicants, real public scholarship research and an owned demo application portal**. A confirmed demo receipt demonstrates the software workflow; it does not mean a university received an application. Scholarship selection, applicant authenticity and admissions outcomes are not guaranteed.

## Neatlogs: observing and improving the agent

Neatlogs is a central part of our development and evaluation workflow. It connects the agent's tool calls and model responses to the evidence we use to understand failures, test changes and manage the drafting prompt. ScholarPilot executes its own bounded planner and tools; Neatlogs makes those runs inspectable and provides the evaluation and prompt-management layer.

### 1. Tracing the actual application workflow

The shared tracing helpers initialize the SDK once per process and wrap the model clients. Workflow, agent, tool, guardrail and recovery spans expose scholarship research, evidence selection, drafting, verification, revision and submission decisions. Application records retain actual trace identifiers so the frontend can link a result to its Neatlogs trace. Shutdown hooks flush and close tracing.

For example, one completed fictional run has **112 spans, 11 LLM calls, 33,537 tokens and 116.568 seconds of execution**, with estimated model cost **$0.0246933**. These are measurements of that particular run, not a promised average price or latency. The [saved run evidence](docs/evidence/agent_after_source_review_20261012.json) records the result. Some older traces have incomplete usage metadata; missing or zero telemetry must not be presented as free model usage.

### 2. Replay, detections and diagnosis

We exercised Neatlogs Replay on a real recorded run to inspect the order of model and tool steps. Six ScholarPilot detection rules were created through Neatlogs MCP; their setup is recorded in [detection evidence](docs/evidence/neatlogs_detection_setup.json). Recovery spans make retries, fallback and handoff decisions visible rather than hiding them behind a final status.

This mattered during development: source review found unsupported causal wording in an earlier draft that both model checks had accepted. The recorded workflow gave us the concrete claim, source and verification decisions to inspect. We then tightened the checks and added regression cases. Tracing helps locate mistakes; it does not establish that every claim is true, and a configured detection rule is not proof that every future failure will be detected.

### 3. Factuality Evals on linked fictional traces

We launched real Neatlogs evaluations using recorded fictional-case traces and a source-grounded rubric. The cases include faithful statements alongside inflated GPA, unsupported causation and future goals incorrectly described as completed accomplishments. The evaluator checks the actual verdict against the provided claim and sources.

The corrected six-case batch completed **six AI reviews, all matching the expected outcomes**: the underlying checks accepted two supported cases and rejected four unsupported cases. Here, an evaluation result of `pass` means the decision was correct; it does not mean an unsupported applicant claim was accepted. [Saved results](docs/evidence/neatlogs_corrected_evals_20261012.json) contain the case identifiers, trace links, verdicts and reasoning.

We also preserve the first 13-item batch, which returned four passes, eight failures and one insufficient-evidence result. A sampled failure incorrectly judged display formatting: structured JSON had been rendered as readable text in the dashboard. We corrected the evaluation scope instead of reporting those results as factuality accuracy. See [the original readback](docs/evidence/neatlogs_evals_readback_20261012.json). These small, curated evaluations are regression evidence, not a general accuracy benchmark or a zero-hallucination guarantee.

### 4. Managed prompts, validation and promotion

The drafting prompt is stored in Neatlogs as `scholarpilot-drafting`. The backend resolves its `production` label and records the selected version and digest. Versions 1 and 2 were compared against fictional sources; both produced zero unsupported segments in that small comparison, so we do **not** claim that version 2 demonstrated superior accuracy.

Version 2 was promoted, used in a subsequent actual model call, and fetched by the AWS runtime with a matching digest. [Prompt comparison and run evidence](docs/evidence/neatlogs_prompt_and_cases_20261012.json) and [AWS readback](docs/evidence/aws_managed_prompt_20261012.json) document this. Rollback is available by moving the production label to the previous saved version. The resolver has an explicit fallback when the managed prompt is unavailable, and mandatory local grounding instructions remain enforced.

Prompt promotion cannot disable our verification requirements. **A deterministic check, an independent judge and the Challenger must all pass before a generated claim is admitted.** Neatlogs Evals supplement those runtime checks; they do not replace them.

### 5. Fixes review and the unfinished dispatch loop

We reviewed an actual Neatlogs Fixes suggestion through MCP. Its proposed deterministic-only acceptance or threshold bypass would weaken verification, so we rejected that approach. The resulting repository work adds diagnostic counts and regression coverage while preserving all three checks. [Fixes readback](docs/evidence/neatlogs_fixes_readback_20261012.json) and [the review PR](https://github.com/Goodyness-dev/uni/pull/2) make that distinction reviewable.

**Native Neatlogs cloud coding-agent dispatch is incomplete.** The PR was created by this Codex session after MCP review. It was not produced by Neatlogs cloud dispatch. Connecting coding-agent credentials does not prove a dispatched job can run: the Claude Code and Codex cloud options were marked “Coming soon” in the inspected dashboard. Investigate also repeatedly lost its connection, including with a configured model provider. We have no completed native investigation-to-dispatched-PR result to claim.

### What Neatlogs changes for this project

The useful loop is concrete: inspect a real run, identify the failing claim or decision, turn it into a regression case, evaluate the change, promote a validated prompt and check what the next run actually used. That makes improvements easier to inspect and repeat. Neatlogs was our chosen integrated platform for this loop; we do not claim it is the only observability product that could support a scholarship agent.

## Work in progress: what the demo does not establish

| Area | Demonstrated so far | Still unfinished or limited |
| --- | --- | --- |
| Applicant intake | PDF/text upload, source review and literal prefill of clear names, emails, GPA/scale and documented subjects; completed details and optional questions collapse | Users run **Parse Facts** and confirm source alignment. Conflicts stay unresolved; nationality is never inferred from university location. Destinations, funding and study plans still need the user's intent. Real-document authenticity and broad document-format coverage are unproven. |
| Agent decisions | Bounded tool selection, research memory, missing-evidence continuation, verification and revisions | This is a bounded agent, not unrestricted autonomous browsing. Broader strategy changes and difficult cases need more evaluation. |
| Scholarship research | Refreshes supplied official sources and records failures and unverified leads | Coverage is limited; blocked pages, changing deadlines and ambiguous eligibility require review. It is not exhaustive live scholarship search. |
| Factuality | Three runtime checks, curated live regression cases and completed Neatlogs Evals | Both model checks have previously accepted an unsupported claim. Larger, diverse and independently reviewed evaluations remain necessary. |
| Neatlogs improvement loop | Real traces, Replay, detection setup, Evals, managed prompt promotion and MCP Fixes review | Investigate completion and a native cloud dispatch producing a tested PR remain incomplete. |
| Portal actions | Confirmed submissions to our owned fictional demo portal | Real scholarship submission is deliberately prohibited. Login and CAPTCHA require human handoff; automated bypass is prohibited. |
| Operations | Local PostgreSQL/Redis integration, a private AWS prototype, selected recovery checks and provider-accepted notification tests | Public production deployment, high availability, total-host recovery and reliable operation at scale are unverified. Provider acceptance does not prove inbox delivery. |
| Identity and privacy | Cognito integration, verified identity evidence, ownership controls and privacy-erasure paths | Sign-in remains dependent on successful verification and callback configuration. Real applicant security, retention, regulatory compliance and production usability require further review. |

Our next priorities are intake and sign-in usability, more adversarial factuality cases, broader authoritative-source research, durable recovery testing and a supported native Fixes dispatch. None of these improvements should weaken the independent judge or Challenger. Treat the current project as a demonstrable hackathon prototype with an evidence trail, not a production scholarship service.

### Latest frontend-to-agent repair

The frontend now sends both PDFs, saves current preferences before matching, preserves form edits during review and continues polling while the separate submission worker is active. Adding missing context to an existing profile no longer requires uploading the CV again. New source edits disable Run until parsing and review are complete. Optional personal-history and notification controls are collapsed.

Provider overload, authentication errors and budget denial are handled separately. An overloaded primary can switch to the configured fallback; the fallback has bounded retries, and a failed budget reservation stops provider execution. The configured backup is `gemini-3.1-flash-lite`, validated with an actual structured completion. A listed `gemini-2.5-flash-lite` model returned 404 for this key, so it was not retained as the backup. Both candidates currently use Gemini: this is model fallback, not an independent provider failover or an uptime guarantee.

The backup also passed a live six-case regression through the same deterministic, judge and Challenger path: two supported claims were retained and four unsupported claims rejected. [Saved fallback results](docs/evidence/fallback_factuality_regression_20261012.json) include actual model usage and a trace ID. Six curated cases do not establish general accuracy or equivalence between models.

A new frontend-driven fictional run completed with owned-portal receipt **DEMO4898**. Its automated report recorded eight accepted claims and zero unsupported final claims under the checks then in use. Subsequent manual review flagged an inferred “technical project leadership” claim that both model checks accepted; a new deterministic regression blocks that wording without explicit source evidence. The receipt proves the owned-portal workflow, not perfect factuality. The smoke test used stored research and the fixture's original study plans. Earlier failed attempts and this manual finding remain in [the receipt, verification and trace evidence](docs/evidence/document_prefill_flow_20261012.json).

If no supported essay survives, the agent requests original missing evidence through the existing handoff and continuation flow. It does not fill missing motivations or future plans from grades. A scholarship word limit is treated as a maximum, not a made-up minimum.

## Two implementations

* `backend/`: the original SQLite/FastAPI demo, `/api/*`, synthetic persona, local demo portal, LLM drafting and verification experiments.
* Root `app/`: SQLAlchemy/PostgreSQL-oriented service, `/v1/*`, user ownership checks, jobs, coordinator and browser scaffold.
* `frontend/`: the existing four Next.js screens support the demo contract and an optional typed v1 adapter. Set `NEXT_PUBLIC_API_VERSION=v1` and `NEXT_PUBLIC_API_BASE` to the root service origin. The v1 adapter disables mocks and sends an API key from session storage; its browser flow has been exercised through real local PostgreSQL, Redis, API, worker and Chromium against the fictional demo portal.

## Root service behavior

1. User-provided profile data is matched against the stored scholarship catalog. Missing eligibility evidence is not invented; ineligible applications stop.
2. Research retains a literal fetched page snippet when available. Failed research yields no inferred institutional facts. Source URLs alone do not prove an institutional priority.
3. Drafting defaults to an extractive baseline. With `LLM_DRAFTING=true`, allowed/disclose AI-policy listings use reviewed source facts, sentence citations, separate judge and Challenger calls, and up to two revisions. Remaining unsupported sentences are removed; empty essays stop. CV PDF, writing material and checklist files are built from stored evidence. Restricted/unknown policies receive original notes for manual writing. Offline tests and a live fictional application exercise this path. Human source review caught errors missed by both model judges; this is not a factuality guarantee.
4. Application creation queues a coordinator job. Review mode stops for approval; approval of an allowed demo application queues submission. Resume performs authoritative confirmation readback after the human submits; it does not click Submit again.
5. The worker polls atomically claimed database jobs with Redis wake-up signals. Internal jobs use bounded retry delays; uncertain external submission outcomes are not automatically retried.
6. Browser submission is restricted to the local demo portal. Drafts use the application ID as an idempotency key. Confirmation is read back from the portal's submission API, including after human handoff. Missing browser support fails clearly; missing confirmation requires human review and blocks automatic resubmission.
7. Demo browser submission requires a renewable Redis application lease and checks the configured/shared kill switch before clicking. This prevents normal concurrent execution but is not a portal-level exactly-once guarantee.
8. The worker schedules catalog matching once per local day/timezone using Redis deduplication. Deadline notifications use stored Telegram chat IDs and delivery deduplication.
9. Owned PDF/text uploads are bounded to 10 MB each and 50 MB per owner. Registration alone remains **unverified**. Applicant review requires literal source/excerpt alignment and records the document digest; a changed file invalidates reviewed evidence. Source alignment does not certify authenticity or grades.
10. Export includes database records and optionally owned document bytes (`include_files=true`, aggregate 20 MB). Erasure removes managed documents, packages, session artifacts and related records; external references are not deleted. Database triggers prohibit normal event updates/deletes, with an explicit owner-scoped privacy erasure exception. Ordinary PostgreSQL audit guards passed local checks; deployment privileges remain unverified.

## Safety and operational limits

* No CAPTCHA/login bypass, real scholarship submission, invented applicant facts, or fabricated success.
* Production key issuance requires a fresh RS256 identity token from a pinned HTTPS issuer/JWKS endpoint, the configured audience, verified matching email and a Redis replay check. Configure `OIDC_ISSUER`, `OIDC_AUDIENCE`, `OIDC_JWKS_URL`; keys enforce read/write scopes. The top bar can exchange an identity-provider token. Provider sign-in/redirect integration remains an operator setup and live validation task. Knowing an email alone cannot recover an existing identity.
* Production model attempts require a known pricing entry, a real key, an owner and a shared Redis budget reservation. These are conservative estimated token bounds; they require live provider/Redis validation before any production spend guarantee.
* Tracing initializes through the shared backend helper in API and worker processes. Draft text is excluded from guardrail spans. Real sponsor dashboard readback verified the bounded agent run: 112 spans and 11 LLM calls. Six ScholarPilot detection rules were created through Neatlogs MCP. Trace links use actual IDs; full content capture is restricted to the fictional fixture.
* Production v1 rate limiting uses shared Redis sliding windows for credentials and client addresses and rejects missing Redis. Forwarding headers are not trusted; reverse-proxy address configuration needs deployment validation. Development uses an in-process limiter.
* Saved browser storage state is not a complete accessible human browser handoff. A headed/persistent handoff session remains unfinished.
* Ordinary state transitions write audit events protected by database guards. This is not immutable retention against privileged database administrators; privacy erasure explicitly deletes owned events.
* Filesystem erasure and database deletion are not a distributed transaction. Redis account-stop keys prevent normal active submissions after erasure begins, but an already accepted submission cannot be undone. External object storage deletion requires additional lifecycle design.
* `LIVE_RESEARCH` defaults off. Enabled research accepts public HTTPS only, rejects private/mixed DNS results, pins the resolved address with the original TLS hostname, follows no redirects and limits content size. Treat snippets as untrusted data. Production egress policy and actual TLS/DNS behavior still need integration validation.

## Running locally

Original demo (from `backend/`): install `backend/requirements.txt`, then `python run_server.py`. Frontend: `cd frontend`, `npm install`, `npm run dev`. Use only the synthetic persona and demo portal.

Root service: install the existing root `requirements.txt`, configure an isolated database/broker, run `alembic upgrade head`, import the catalog with `python scripts/import_catalog.py`, then start `uvicorn app.main:app`. Start the worker separately with `python -m app.worker`.

The private AWS prototype has been deployed in eu-north-1 using `deploy/aws-private.json` and the six-service `deploy/compose.yml`: PostgreSQL, Redis, API, worker, frontend and owned demo portal. Runtime secrets are private and database/cache ports have no inbound exposure. **Public, highly available production deployment and total-host recovery have not been validated.** See [operations and costs](docs/AWS_LOCAL_OPERATIONS.md). Existing deployments at migration 001 must run the forward repair migration; changing an applied migration is insufficient.

## Tests and validation

Run `python -m pytest tests/ -q` for the root service and `python scripts/quick_check.py` from `backend/` for the original demo. The root tests use fictional fixtures, fake Redis and HTTP doubles; no provider keys or real portal submissions are required.

The complete priority plan and acceptance checks are in [docs/PRODUCTION_REPAIR_PLAN.md](docs/PRODUCTION_REPAIR_PLAN.md). Read the final verification report there for measured test results and pending live checks. Passing SQLite/unit tests does not establish PostgreSQL/Redis/Playwright behavior in production.

## Evidence

Earlier offline evaluation JSON files under `docs/evidence/` report zero LLM calls/tokens/cost. Those are demo artifacts and do not establish measured live-model unit economics, a zero-hallucination guarantee, deployed sponsor detection rules or regulatory compliance. The earlier claims of 15 deployed detections, measured $0.0025/application, 99.9% margins and complete NDPR/GDPR compliance have been removed pending verifiable evidence.

No unverified video, sponsor-project or dashboard placeholder links are presented as published proof.

## Verified local integration

The fictional Tobi application completed through the existing frontend, root API, worker, PostgreSQL 16.11, Redis 7.4.9 and actual Chromium. The worker read authoritative demo confirmation **DEMO1668**. A separate confirmation-only handoff produced **DEMO4907**. Actual evidence is in `docs/evidence/fictional_e2e_20261012.json`; this establishes local development integration, not production deployment or live-model quality.

On the configured Windows workstation, run `backend/.venv/Scripts/python.exe scripts/local_demo.py start`; open http://localhost:3000. Use `stop` to stop the recorded local processes, or `scripts/verify_local_demo.py` to recollect evidence. This uses portable runtime binaries and random credentials beneath ignored `storage/local_runtime`; it does not register Windows services. The default launcher disables paid providers, public research and external notifications, imports only the challenge-free fictional portal listing, and uses a separate portal SQLite database. PostgreSQL runs with a privileged development role.

Frontend `.env.local` is configured for v1, mocks off, an empty public API base and `API_BACKEND_URL=http://127.0.0.1:8001`. The local launcher supplies these same values. Session keys remain in browser session storage, so a fresh tab needs to connect its existing key or create a new fictional identity in development. Production identity issuance remains token-protected.

## Agent expansion validation

The agent now has nine bounded actions and persistent research snapshots, missing-evidence continuation, cancellation before demo submission, real file-drop controls, actual email/Telegram delivery jobs and a Cognito PKCE sign-in redirect. Live discovery refreshes supplied official sources and saves unverified leads. It corrected closed Chevening/Rhodes cycles and the Commonwealth cutoff; unavailable pages remain explicit failures. This is bounded discovery, not unrestricted internet search or certified institutional eligibility.

The live 32-case fictional evaluation accepted 11 supported claims and rejected 21 unsupported claims, including two previously accepted error categories. This curated result is not a factuality guarantee. Queued local email and Telegram tests completed with provider acceptance, and an AWS SES test succeeded using the instance role; inbox placement is not verified. The real Commonwealth preparation stopped at applicant handoff and Cambridge portal inspection stopped at login. No real scholarship application was submitted.

See the current [reality audit](docs/AGENT_REALITY_AUDIT.md), [approved contract extensions](docs/PRODUCTION_V1_CONTRACT.md), and [evidence](docs/evidence). Verified onboarding is complete only after the user finishes Cognito signup, emailed verification and the callback; reaching its sign-in page does not establish that result.

Portable runtime sources: [PostgreSQL Windows binaries](https://www.enterprisedb.com/download-postgresql-binaries), [Redis Windows 7.4.9 release and checksum](https://github.com/redis-windows/redis-windows/releases/tag/7.4.9). The Redis distribution is a Windows build, not a Linux deployment validation.

## Live bounded agent demo

Run `backend/.venv/Scripts/python.exe scripts/local_demo.py start --agent` to enable the real model path. The planner selects allowed tools, fetches the owned portal requirements, selects reviewed evidence, drafts, independently verifies and revises, then queues automatic submission to the owned demo portal when Autopilot is on. The existing profile screen exposes an Autopilot checkbox; turn it off to require review. The submission service checks an owner-scoped Redis pause marker before automatic Submit. Model attempts use Redis budget reservations; source citations and decisions appear in the existing application screen.

The improved fictional application completed with receipt **DEMO1584**. Neatlogs finalized trace `7aeb442a172e5c5179639b86fa39f867`: **112 spans, 11 LLM calls, 33,537 tokens, 116.568 seconds**, estimated model cost **$0.0246933**. Replay was exercised on this actual trace. The earlier draft remained unsubmitted after manual review found unsupported causal wording; regression checks and stricter judges were added before the new run. This pair is an improvement example, not an accuracy benchmark.

See [Neatlogs agent demo](docs/NEATLOGS_AGENT_DEMO.md) and [live evidence](docs/evidence/agent_after_source_review_20261012.json). Investigate loaded the real traces but its summary lost connection after a pagination loop; no completed investigation is claimed. Neatlogs AI evaluations were subsequently completed as described above. Production readiness, real applicant safety and general model reliability remain unverified.

### Neatlogs improvement loop

Managed drafting prompts are fetched by the production label; version 2 was compared on fictional sources, promoted and used by a subsequent real model call, with AWS runtime readback. Real Neatlogs Evals were launched with linked fictional traces. The first batch also exposed false format judgments from readable trace rendering, so it is not claimed as factuality accuracy. An actual Fixes suggestion was reviewed through MCP; its proposed weaker verification was rejected. Native coding-agent dispatch is not complete. See [measured results and limits](docs/NEATLOGS_IMPROVEMENT_PLAN.md).
