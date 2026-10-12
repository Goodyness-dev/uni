# ScholarPilot

ScholarPilot is a scholarship application assistant built for neatHack, October 10–12, 2026. Memeshi works on backend/agents and Ayo on the frontend.

**Current status: development prototype with production repair work in progress. It is not ready for real applicant data or real scholarship submissions.**

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

See [Neatlogs agent demo](docs/NEATLOGS_AGENT_DEMO.md) and [live evidence](docs/evidence/agent_after_source_review_20261012.json). Investigate loaded the real traces but its summary lost connection after a pagination loop; no completed investigation or AI evaluation is claimed. Production deployment, real applicant safety and model reliability remain unverified.
