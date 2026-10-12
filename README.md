# ScholarPilot

ScholarPilot is a scholarship application assistant built for neatHack, October 10–12, 2026. Memeshi works on backend/agents and Ayo on the frontend.

**Current status: development prototype with production repair work in progress. It is not ready for real applicant data or real scholarship submissions.**

## Two implementations

* `backend/`: the original SQLite/FastAPI demo, `/api/*`, synthetic persona, local demo portal, LLM drafting and verification experiments.
* Root `app/`: SQLAlchemy/PostgreSQL-oriented service, `/v1/*`, user ownership checks, jobs, coordinator and browser scaffold.
* `frontend/`: Next.js frontend for the original `/api/*` contract. It defaults to mocks unless `NEXT_PUBLIC_USE_MOCKS=false`. It is not connected to `/v1/*`.

## Root service behavior

1. User-provided profile data is matched against the stored scholarship catalog. Missing eligibility evidence is not invented; ineligible applications stop.
2. Research retains a literal fetched page snippet when available. Failed research yields no inferred institutional facts. Source URLs alone do not prove an institutional priority.
3. The current drafter is an **extractive baseline**: original profile descriptions are copied with conservative support checks. It is not an LLM essay writer, adversarial Challenger, or a complete CV/package generator.
4. Application creation queues a coordinator job. Review mode stops for approval; approval/resume queue submission jobs.
5. The worker polls atomically claimed database jobs with Redis wake-up signals. Internal jobs use bounded retry delays; uncertain external submission outcomes are not automatically retried.
6. Browser submission is restricted to the local demo portal. Missing browser support fails clearly. A real confirmation must be read from the page. Missing confirmation requires human review.
7. Real submission requires a Redis application lease and checks the configured/shared kill switch before clicking. This prevents normal concurrent execution but is not a portal-level exactly-once guarantee.
8. The worker schedules catalog matching once per local day/timezone using Redis deduplication. Deadline notifications use stored Telegram chat IDs and delivery deduplication.
9. Document registration accepts existing files only inside `storage/documents/<user UUID>/`. Metadata is explicitly **unverified**; no authenticity, GPA or applicant fact is certified by a file type.
10. Export contains selected database records and document references, not a complete archive of file contents. Erasure removes managed artifacts and related records; legacy external file paths are never deleted. Workflow events are erased for privacy rather than retained permanently.

## Safety and operational limits

* No CAPTCHA/login bypass, real scholarship submission, invented applicant facts, or fabricated success.
* Production API-key issuance is disabled until a verified identity onboarding flow is implemented. Knowing an existing user's email cannot mint a new key.
* Production model attempts require a known pricing entry, a real key, an owner and a shared Redis budget reservation. These are conservative estimated token bounds; they require live provider/Redis validation before any production spend guarantee.
* Tracing initializes through the shared backend helper in API and worker processes. Draft text is excluded from guardrail spans. Actual sponsor dashboard coverage/deep links still require a live verification run.
* Rate limiting is connected to v1 routes but remains per process. Identity scopes, shared rate limiting and trusted proxy configuration need further hardening.
* Saved browser storage state is not a complete accessible human browser handoff. A headed/persistent handoff session remains unfinished.
* Ordinary state transitions write audit events. Immutable audit retention/database permissions are not implemented; privacy erasure explicitly deletes events.
* Filesystem erasure and database deletion are not a distributed transaction. Concurrent active-work erasure and external object storage deletion require additional lifecycle design.
* Public research URL checks are preliminary. Controlled network egress and DNS/redirect validation are required before enabling research on arbitrary untrusted URLs.

## Running locally

Original demo (from `backend/`): install `backend/requirements.txt`, then `python run_server.py`. Frontend: `cd frontend`, `npm install`, `npm run dev`. Use only the synthetic persona and demo portal.

Root service: install the existing root `requirements.txt`, configure an isolated database/broker, run `alembic upgrade head`, import the catalog with `python scripts/import_catalog.py`, then start `uvicorn app.main:app`. Start the worker separately with `python -m app.worker`.

Docker Compose describes Postgres, Redis, API and worker services. **A working production deployment has not been validated.** Default development credentials must be replaced and database/broker ports kept private before deployment. Existing deployments at migration 001 must run the forward repair migration; changing an applied migration is insufficient.

## Tests and validation

Run `python -m pytest tests/ -q` for the root service and `python scripts/quick_check.py` from `backend/` for the original demo. The root tests use fictional fixtures, fake Redis and HTTP doubles; no provider keys or real portal submissions are required.

The complete priority plan and acceptance checks are in [docs/PRODUCTION_REPAIR_PLAN.md](docs/PRODUCTION_REPAIR_PLAN.md). Read the final verification report there for measured test results and pending live checks. Passing SQLite/unit tests does not establish PostgreSQL/Redis/Playwright behavior in production.

## Evidence

Saved evaluation JSON files under `docs/evidence/` report zero LLM calls/tokens/cost. They are demo artifacts and do not establish measured live-model unit economics, a zero-hallucination guarantee, deployed sponsor detection rules or regulatory compliance. The earlier claims of 15 deployed detections, measured $0.0025/application, 99.9% margins and complete NDPR/GDPR compliance have been removed pending verifiable evidence.

No unverified video, sponsor-project or dashboard placeholder links are presented as published proof.
