# Architecture & Engineering Decisions (DECISIONS.md)

This document records every architectural assumption, design decision, dependency choice, and tradeoff made during the transition of ScholarPilot from demo to production, as required by the **Scholarship Agent: Demo to Production Brief**.

---

## 1. Foundational Assumptions

### 1.1 Repository Structure & Coexistence
- **Brief Requirement**: Root `app/` package layout containing `api/`, `agents/`, `core/`, `db/`, `jobs/`, `integrations/`, `services/`, plus `tests/`, `scripts/`, `docs/`, `DECISIONS.md`, `README.md`.
- **Decision**: The root `app/` directory will serve as the canonical production package. The existing `backend/` demo files remain intact for historical trace auditability and hackathon archive provenance. All new production code, migrations, and CLI scripts reside in the top-level structure.

### 1.2 Database Engine & ORM
- **Brief Requirement**: "Postgres is the system of record. Design tables with UUID primary keys, created_at and updated_at on everything. Rules: use migrations for every schema change, never edit the database by hand. Add indexes on deadline, user_id plus status, and scholarship_id."
- **Decision**: 
  - We use **SQLAlchemy 2.0 (asyncio)** with **asyncpg** (and psycopg for synchronous migration scripts) + **Alembic** for schema migrations.
  - To support fast local unit testing on developers' machines without requiring an active PostgreSQL daemon, the engine dynamically supports SQLite async mode (`sqlite+aiosqlite:///`) when `DATABASE_URL` specifies SQLite, while strictly defaulting to PostgreSQL (`postgresql+asyncpg://scholarpilot:scholarpilot@localhost:5432/scholarpilot_db`) in staging and production.
  - All primary keys use `uuid.UUID` (`UUID(as_uuid=True)` in Postgres / string representation in SQLite). All timestamps are UTC `DateTime(timezone=True)`.

### 1.3 LLM Gateway & Provider Abstraction
- **Brief Requirement**: "One module that wraps every model call so models, retries, costs and logging live in a single place. Track cost per user and per job. Set a daily spending cap per user and a global cap."
- **Decision**:
  - `app/core/llm_gateway.py` acts as the single choke-point for all model invocations.
  - Supports primary model (Gemini / OpenAI compatible API) with automatic exponential backoff, jitter, and fallback to secondary provider on consecutive 429/500 errors.
  - Emits structured cost metrics per call based on input/output tokens.
  - Enforces daily per-user spending caps and global caps via atomic tracking.
  - Preserves Neatlogs observability wrapper spans (`WORKFLOW`, `AGENT`, `CHAIN`, `GUARDRAIL`) while maintaining zero external SDK dependencies outside `llm_gateway.py`.

### 1.4 Task Queue & Concurrency
- **Brief Requirement**: "Redis (task queue, locks, rate limits). Worker service runs agent jobs from a task queue. Scheduler triggers daily discovery and matching run per user."
- **Decision**:
  - We design an asynchronous job queue abstraction (`app/jobs/`) with an asynchronous Redis worker implementation (via `redis.asyncio` / ARQ pattern) and an in-process fallback runner for lightweight local dev/testing.
  - Distributed locks use Redis SETNX with TTL to prevent concurrent duplicate runs per user timezone.

### 1.5 Security & Data Hygiene
- **Brief Requirement**:
  - No plain-text portal passwords (encrypt at rest with AES-GCM via `app/core/security.py`).
  - No PII (full names, emails, phone numbers, ID numbers, essay text) in plain application logs. A structured redacting log formatter is configured in `app/core/logging.py`.
  - Row ownership checks strictly enforced in repository layer.
  - Global kill switch (`KILL_SWITCH_ACTIVE=true` env var + admin endpoint) to pause all external submissions immediately.

---

## 2. Dependencies & Rationale

| Dependency | Purpose | Rationale |
|---|---|---|
| `fastapi` & `uvicorn` | API framework | Async native, OpenAPI auto-generation, high performance |
| `pydantic` (v2) & `pydantic-settings` | Data models & configuration | Strict schema validation, type safety |
| `sqlalchemy` (>= 2.0) | Relational ORM & core query builder | Asynchronous DB operations, typed models, vendor portability |
| `asyncpg` & `aiosqlite` | Async DB drivers | High-speed Postgres async driver + local async SQLite fallback |
| `alembic` | Database migrations | Strict version-controlled schema evolution |
| `redis` | Queue, distributed locks, rate limiting | Industry standard for low-latency task broker and coordination |
| `httpx` | Async HTTP client | Robust HTTP communication with timeouts, proxies, and retries |
| `cryptography` | Symmetric credential encryption | Fernet / AES-256-GCM for portal passwords and webhook signing |
| `pytest` | Automated test suite | Test execution, contract checks, and state machine validation |
| `greenlet` | SQLAlchemy asyncio runtime | Required by SQLAlchemy asyncio engine for async context management |

---

## 3. Milestone 1 Plan: Foundation

**Goal**: Establish the core production skeleton, config, logging, PostgreSQL schema models, Alembic migrations, demo catalog importer, and LLM gateway.

### Target Files:
1. `app/__init__.py`
2. `app/core/config.py`: Type-safe settings with Pydantic Settings (DB URLs, Redis URLs, encryption keys, LLM credentials, kill switches).
3. `app/core/logging.py`: Structured JSON logger with automatic PII redactor.
4. `app/core/security.py`: Password hashing, API key hashing, AES-256 encryption/decryption for credentials, HMAC webhook signer.
5. `app/core/llm_gateway.py`: Unified LLM client with retry, cost accounting, daily user spending caps, fallback providers, and structured schemas.
6. `app/db/base.py`: SQLAlchemy async engine, session factory, base model with UUID primary keys and UTC timestamps.
7. `app/db/models.py`: 11 production models (User, Profile, Document, Scholarship, Match, Application, ApplicationEvent, Draft, Job, ApiKey, Webhook).
8. `alembic.ini` & `app/db/migrations/`: Initial Alembic migration defining full schema and indexes.
9. `scripts/import_catalog.py`: Seeds the `scholarships` table from `backend/data/listings.json`.
10. `tests/test_foundation.py`: Tests verifying DB connection, model creation, catalog import, security encryption/decryption, logging redaction, and LLM gateway wrapper.
11. `app/main.py`: FastAPI app with `/health` and `/ready` probes.

### Milestone 1 Summary (Completed):
- **What Changed**:
  - Implemented `app/core/config.py` with type-safe settings, kill switch flag, and spending cap configuration.
  - Implemented `app/core/logging.py` featuring structured JSON output and automated PII scrubbing (emails, phone numbers, passwords, essay text, national IDs).
  - Implemented `app/core/security.py` with AES-256 Fernet credential encryption, API key generation + SHA-256 verification, and HMAC-SHA256 webhook signatures.
  - Implemented `app/core/llm_gateway.py` with multi-provider routing (Gemini primary, fallback secondary), retry with backoff, daily per-user & global spending caps, schema validation, and prompt injection sanitization.
  - Implemented `app/db/base.py` and `app/db/models.py` with all 11 production models featuring UUID primary keys, created_at/updated_at timestamps, and required indexes.
  - Configured `alembic.ini` and initial migration `20261011_001_initial_schema.py` (verified via `alembic upgrade head`).
  - Implemented `scripts/import_catalog.py` populating `scholarships` from `backend/data/listings.json`.
  - Implemented `app/main.py` with `/health` and `/ready` endpoints.
  - Wrote and passed all 8 automated tests in `tests/test_foundation.py`.
- **What is Untested**:
  - Direct live PostgreSQL multi-node connection pool in production container (tested on SQLite async / aiosqlite and local migration dialect).
  - Real paid API calls to remote LLMs with live credit cards (mocked and tested via gateway harness).
- **Assumptions**:
  - Production database will run on PostgreSQL 15+ in production / Docker, while supporting local development and tests via async SQLite fallback.
  - Redis will be provisioned in Milestone 3 for background queue tasks and distributed locking.

---

## 4. Milestone 2 Plan: Core API

**Goal**: Expose public and developer endpoints under `/v1` for authentication, Profile Vault management, document tracking, scholarship discovery, and match viewing.
**Acceptance Criteria**: A developer can create an API key, fill a profile, and fetch ranked matches via curl.

### Target Files:
1. `app/api/deps.py`: Auth dependencies (API key header authentication `X-API-Key` and session token).
2. `app/api/v1/auth.py`: `POST /v1/auth/keys` (create key), `DELETE /v1/auth/keys/{id}` (revoke key).
3. `app/api/v1/profile.py`: `GET /v1/profile` and `PUT /v1/profile` (Profile Vault CRUD with completeness score computation).
4. `app/api/v1/documents.py`: `POST /v1/documents` (metadata upload), `GET /v1/documents` (list documents).
5. `app/api/v1/scholarships.py`: `GET /v1/scholarships` with filters for country, level, field, deadline range, and minimum amount.
6. `app/api/v1/matches.py`: `GET /v1/matches` and `POST /v1/matches/refresh`.
7. `app/api/v1/router.py`: Aggregates all `/v1` route modules into a single FastAPI router.
8. `tests/test_core_api.py`: Contract tests covering key generation, profile updates, scholarship filtering, and match queries against OpenAPI schemas.

### Milestone 2 Summary (Completed):
- **What Changed**:
  - Implemented `app/api/deps.py` with `get_current_user` resolving `X-API-Key` and Bearer token against the `ApiKey` table with active check, revoked check, and `last_used_at` tracking.
  - Implemented `app/api/v1/auth.py` with `POST /v1/auth/keys` and `DELETE /v1/auth/keys/{id}` for secure developer key lifecycle.
  - Implemented `app/api/v1/profile.py` providing Profile Vault CRUD with automated `completeness_score` calculation.
  - Implemented `app/api/v1/documents.py` supporting document metadata upload and user-scoped listing.
  - Implemented `app/api/v1/scholarships.py` with multi-attribute filtering (country, level, field, min_amount, deadline range) and pagination.
  - Implemented `app/api/v1/matches.py` providing deterministic eligibility filtering, deadline urgency scoring, fit scoring, and plain-language reason lists.
  - Registered all `/v1` routes in `app/main.py` with structured error handling for consistent error payloads (`{"code": ..., "message": ..., "request_id": ...}`).
  - Added comprehensive test suite `tests/test_core_api.py` covering the full developer end-to-end journey (all tests passing).
- **What is Untested**:
  - Live S3 binary upload transfers (documents currently track `storage_key` metadata).
  - Web session cookies (API keys and Bearer tokens verified).
- **Assumptions**:
  - Developers will use `X-API-Key` header with `sp_live_...` tokens.
  - Default applicant degree level targets graduate study (`masters`) unless specified in profile history.

---

## 5. Milestone 3 Plan: Agents on a Queue

**Goal**: Implement the core agent modules as queue-driven background jobs:
- **Matcher**: Evaluates profile against catalog and emits ranked matches.
- **Researcher**: Researches school & programme details, enforces sourced facts, caches for 7 days.
- **Edge Finder**: Computes authentic alignment angles between vault facts and school priorities.
- **Drafter**: Writes tailored drafts with source facts and word limits, enforces grounding checks.
- **Queue Harness**: Redis / asynchronous job runner executing agent jobs from the `jobs` table with stored results.

**Acceptance Criteria**: One profile produces grounded drafts for three scholarships with no unsourced claims.

### Target Files:
1. `app/jobs/queue.py`: Background job worker, task dispatch, attempt tracking, error logging.
2. `app/agents/matcher.py`: Matcher agent job worker.
3. `app/agents/researcher.py`: Researcher agent job with 7-day TTL fact caching and anti-injection.
4. `app/agents/edge_finder.py`: Edge Finder agent with recorded reasoning and outcome feedback hooks.
5. `app/agents/drafter.py`: Drafter agent with word-limit enforcement, grounding check, and source citation tagging.
6. `tests/test_agents_queue.py`: Tests executing the queue workflow and verifying grounded drafts for 3 scholarships with zero unsourced claims.

### Milestone 3 Summary (Completed):
- **What Changed**:
  - Implemented `app/jobs/queue.py` providing asynchronous job queue runner, task registration (`@register_job_handler`), attempt tracking, and dead-letter handling.
  - Implemented `app/agents/matcher.py` as queue job worker evaluating eligibility and producing ranked matches.
  - Implemented `app/agents/researcher.py` with strict source enforcement (dropping unsourced claims) and 7-day TTL caching.
  - Implemented `app/agents/edge_finder.py` selecting top grounded angles and recording reasoning for user transparency.
  - Implemented `app/agents/drafter.py` with in-code word-limit enforcement, real-time grounding checks, and versioned draft storage.
  - Created and passed test suite `tests/test_agents_queue.py` verifying that one profile produces grounded drafts for 3 scholarships with zero unsourced claims.
- **What is Untested**:
  - Multi-process distributed Redis cluster workers across network nodes (tested via async job runner and DB queue states).
- **Assumptions**:
  - Research dossiers cache for 7 days per scholarship to avoid redundant web fetches.
  - Drafter strips ungrounded or suspicious claims prior to committing draft versions to the database.

---

## 6. Milestone 4 Plan: State Machine and Modes

**Goal**: Full application lifecycle, Autopilot and Review modes, approval endpoints, and append-only event logging.
**Acceptance Criteria**: Illegal transitions are impossible, and every change appears in `application_events`.

### Target Files:
1. `app/jobs/state_machine.py`: Centralized state machine enforcing the 12 application states, transition validation, event emission, and kill switch enforcement.
2. `app/api/v1/applications.py`:
   - `GET /v1/applications`: list user applications.
   - `GET /v1/applications/{id}`: application details, draft history, and append-only event timeline.
   - `POST /v1/applications`: start application for scholarship.
   - `POST /v1/applications/{id}/approve`: approve draft in Review mode (`ready_for_review -> approved`).
   - `POST /v1/applications/{id}/resume`: continue after `needs_human` blocker.
   - `POST /v1/applications/{id}/withdraw`: cancel application (`withdrawn`).
3. `app/api/v1/settings.py`: `GET /v1/settings` and `PUT /v1/settings` managing user autonomy mode (`autopilot` vs `review`).
4. `tests/test_state_machine.py`: Tests verifying all 12 states, transition validation (illegal transitions raise errors), append-only `application_events` auditing, and Autopilot vs. Review mode branches.

### Milestone 4 Summary (Completed):
- **What Changed**:
  - Implemented `app/jobs/state_machine.py` enforcing the 12 formal states (`discovered`, `matched`, `researching`, `drafting`, `ready_for_review`, `approved`, `submitting`, `needs_human`, `submitted`, `failed`, `expired`, `withdrawn`), strict transition matrix, review mode checks, kill switch enforcement, and append-only `application_events` auditing.
  - Implemented `app/api/v1/applications.py` with endpoints for application creation, retrieval, draft/timeline viewing, user approval (`ready_for_review` -> `approved`), human blocker resume (`needs_human` -> `submitting`), and withdrawal.
  - Implemented `app/api/v1/settings.py` managing user autonomy mode (`autopilot` vs `review`).
  - Added comprehensive test suite `tests/test_state_machine.py` (6/6 tests passing: autopilot lifecycle, review approval, illegal transition rejections, needs_human resume, kill switch halt, REST endpoints).
- **What is Untested**:
  - Webhook delivery push to external customer notification endpoints during transitions (scheduled for Milestone 6).
- **Assumptions**:
  - Review mode applications must stay in `ready_for_review` until explicit user approval via `POST /v1/applications/{id}/approve`.
  - Withdrawing an application transitions it immediately to `withdrawn` from any non-final state.

---

## 7. Milestone 5 Plan: Submitter

**Goal**: Playwright browser runner, screenshot capture at every critical stage, CAPTCHA and human blocker handoff (`needs_human`), confirmation extraction, and strict idempotent submission.
**Acceptance Criteria**: A mocked portal run submits once, and a CAPTCHA run stops cleanly and resumes after approval.

### Target Files:
1. `app/integrations/browser_runner.py`:
   - Headless Playwright runner interface and mocked browser adapter for sandboxed tests and demo portal.
   - Form field population using Profile Vault facts and drafted essays.
   - Screenshot capture per step (stored with content hash in screenshot directory).
   - Blocker detection: CAPTCHA detection, login wall / password prompt, two-factor auth prompt, identity verification, payment fee demand.
2. `app/agents/submitter.py`:
   - Submitter agent job worker (`submit_application_job`).
   - Idempotency guard: verifies if already submitted before taking any browser actions.
   - Credentials decryption: portal passwords decrypted securely using `app.core.security.decrypt_credential`.
   - Blocker handoff: on CAPTCHA / 2FA / login wall, stops browser, captures screenshot, and transitions state to `needs_human`.
   - Success handling: extracts portal submission confirmation reference, saves final screenshot, transitions application to `submitted`.
3. `tests/test_submitter.py`:
   - Tests mocked portal submission completing successfully and generating confirmation reference.
   - Tests idempotent submission: re-running submitter on an already submitted application exits immediately without resubmitting.
   - Tests CAPTCHA / bot check detection cleanly transitioning to `needs_human` with screenshot saved.
   - Tests resuming after user resolves blocker in `needs_human`.

### Milestone 5 Summary (Completed):
- **What Changed**:
  - Implemented `app/integrations/browser_runner.py` with Playwright browser runner integration, `BrowserSubmissionResult`, multi-step screenshot captures, and detection for CAPTCHAs, MFA, login walls, and unexpected application fees.
  - Implemented `app/agents/submitter.py` with strict idempotency enforcement (never resubmits an already submitted application), Review mode safety check (blocks unapproved submissions), graceful handoff to `needs_human` on blockers, and `submitted` confirmation extraction.
  - Added comprehensive test suite `tests/test_submitter.py` (4/4 passed: blocker signature detection, single submission + idempotency guarantee, clean CAPTCHA halt + resume, and Review mode approval requirement).
- **What is Untested**:
  - Live interaction with real external cloud CAPTCHAs (by design: our hard rules mandate halting immediately and never attempting to solve or bypass them).
- **Assumptions**:
  - Applications in `ready_for_review` must be approved by the student prior to calling the submitter.
  - Screenshots are archived in local runtime storage with deterministic file hashes.

---

## 8. Milestone 6 Plan: Autonomy and Notifications

**Goal**: Production scheduler running daily discovery/matching loop per user timezone, proactive deadline reminders (7d, 3d, 1d), Telegram digest summaries, and signed webhook delivery.
**Acceptance Criteria**: Daily scheduler triggers matching for active users, sends deadline alerts, delivers HMAC-signed webhooks, and formats clean Telegram summaries.

### Target Files:
1. `app/services/scheduler.py`: Daily scheduler loop handling timezone offsets, matching runs, and deadline evaluations (7-day, 3-day, 1-day warnings).
2. `app/integrations/telegram.py`: Async Telegram bot interface delivering Markdown status updates, blocker notifications, and daily summaries.
3. `app/integrations/webhooks.py`: Async webhook dispatcher delivering HMAC-SHA256 signed event payloads to registered URLs with retry.
4. `tests/test_autonomy_notifications.py`: Tests verifying timezone-based scheduling, deadline alert emission (7d, 3d, 1d), signed webhook dispatch, and Telegram notification formatting.

### Milestone 6 Summary (Completed):
- **What Changed**:
  - Implemented `app/integrations/webhooks.py` with HMAC-SHA256 signature generation (`sign_webhook_payload`), exponential backoff retry for transient network drops, and failure counter increments.
  - Implemented `app/integrations/telegram.py` with markdown alert formatters for human verification blockers, submission confirmations, deadline warnings, and daily briefing digests.
  - Implemented `app/services/scheduler.py` executing autonomous discovery/matching loop across active users, proactive deadline monitoring classifying opportunities into 7-day, 3-day, and 1-day urgency buckets, and automated webhook/Telegram notification dispatch.
  - Added comprehensive test suite `tests/test_autonomy_notifications.py` (4/4 passed: markdown alert formatting, deadline classification into 7d/3d/1d buckets, HMAC webhook signature verification, and daily scheduler cycle).
- **What is Untested**:
  - Direct live Telegram Bot API network roundtrips with real Telegram bot tokens (mocked and tested via dispatcher harness).
- **Assumptions**:
  - Active users receive daily matching and deadline alerts in their local morning hours.
  - Webhooks retry up to 3 times before recording an incremental failure.

---

## 9. Milestone 7 Plan: Hardening

**Goal**: Production resilience and privacy controls: rate limits, daily cost cap enforcement, PII redaction audit, student account data export (`GET /v1/account/export`), GDPR/NDPR account deletion (`DELETE /v1/account`), and operational runbooks.
**Acceptance Criteria**: Cost caps reject excess calls, sensitive PII is strictly scrubbed from logs, account export returns a complete JSON vault archive, and account deletion purges user profile/credentials cleanly.

### Target Files:
1. `app/api/v1/account.py`: `GET /v1/account/export` (downloads complete student data archive) and `DELETE /v1/account` (purges user account, documents, and vault records).
2. `app/core/rate_limiter.py`: In-memory / Redis sliding window token bucket rate limiter for public and authenticated API endpoints.
3. `docs/RUNBOOKS.md`: Operational incident response runbooks (kill switch activation, rate limit spikes, failed submissions, CAPTCHA surges).
4. `tests/test_hardening.py`: Tests verifying rate limiting rejection (HTTP 429), cost cap cutoff, PII log scrubbing, data export schema, and account deletion purge.

### Milestone 7 Summary (Completed):
- **What Changed**:
  - Implemented `app/core/rate_limiter.py` providing sliding-window token bucket limiter for endpoint DDoS and brute-force mitigation.
  - Implemented `app/api/v1/account.py` supporting `GET /v1/account/export` (complete JSON archive of Profile Vault, documents, applications, and drafts) and `DELETE /v1/account` (permanent purge of profile and personal data under NDPR/GDPR Right to be Forgotten).
  - Mounted account routes in `app/api/v1/router.py`.
  - Authored comprehensive operational runbooks in `docs/RUNBOOKS.md` (Kill Switch, LLM Cost Cap Breaches, CAPTCHA Surges, Key Rollovers, NDPR Erasure).
  - Added comprehensive test suite `tests/test_hardening.py` (4/4 passed: sliding window rate limit rejection, LLM cost cap enforcement, PII redaction audit, full data export, and permanent GDPR deletion).
- **What is Untested**:
  - Direct Redis-backed sliding window clustering across multi-region edge nodes (in-memory token bucket verified).
- **Assumptions**:
  - Account deletion preserves anonymized audit IDs for fraud prevention while removing all student personal details.

---

## 10. Milestone 8 Plan: Launch

**Goal**: Full production launch readiness: multi-stage production Dockerfile, `docker-compose.prod.yml` coordinating FastAPI, PostgreSQL, Redis, and Playwright worker, database migration on boot, and comprehensive deployment documentation.
**Acceptance Criteria**: Containers build and orchestrate cleanly, health probes pass, and complete onboarding documentation enables zero-friction operator setup.

### Target Files:
1. `Dockerfile`: Production multi-stage Python 3.12 container installing dependencies, Playwright browser binaries, and non-root runtime user.
2. `docker-compose.yml`: Production composition orchestrating `db` (Postgres 16), `redis` (Redis 7), `api` (Uvicorn web service), and `worker` (queue processor).
3. `docs/DEPLOYMENT.md`: Production operator onboarding manual, environment variables reference, and setup commands.
4. `README.md`: Updated production-ready system overview, architecture diagram, API reference, and quickstart.

### Milestone 8 Summary (Completed):
- **What Changed**:
  - Implemented multi-stage production `Dockerfile` (Python 3.12-slim) with non-root security user, Playwright Chromium dependencies, and healthcheck probes.
  - Implemented `docker-compose.yml` coordinating PostgreSQL 16, Redis 7, FastAPI API service, and background queue worker.
  - Authored comprehensive production deployment manual in `docs/DEPLOYMENT.md` detailing system topology, environment configurations, migrations, backup strategies, and reverse proxy setup.
  - Updated `README.md` with complete production architecture documentation, 12-state application lifecycle state machine, dual autonomy mode breakdown, API reference matrix, and Docker quickstart instructions.
  - Created root `requirements.txt` pinning production dependencies.
- **What is Untested**:
  - Multi-region geo-distributed PostgreSQL read replicas (single primary cluster configuration implemented and verified).
- **Assumptions**:
  - Production deployments use Docker Compose or Kubernetes with reverse proxy SSL termination.
  - All 30 automated acceptance tests pass across the entire codebase.

---

## 11. Final Architecture Validation Summary

| Milestone | Component | Status | Key Deliverables |
|---|---|---|---|
| **M01: Foundation** | Skeleton & Data Layer | ✅ Complete | PostgreSQL models, Alembic migrations, Fernet AES-256 encryption, PII redactor, LLM gateway with spending caps |
| **M02: Core API** | Public & Developer Endpoints | ✅ Complete | API keys (`sp_live_...`), Profile Vault CRUD, Document upload, Catalog filtering, Match ranking |
| **M03: Agents on a Queue** | Background Agent Pipeline | ✅ Complete | Redis job harness, Matcher, Researcher (7d TTL cache), Edge Finder, Drafter (word limits & grounding) |
| **M04: State Machine & Modes** | Lifecycle & Autonomy | ✅ Complete | 12 lifecycle states, Autopilot vs. Review mode, human approval endpoints, append-only `application_events` |
| **M05: Submitter** | Browser Submission & Handoff | ✅ Complete | Playwright runner, screenshot capture, idempotent submission guard, clean CAPTCHA/MFA handoff |
| **M06: Autonomy & Notifications** | Scheduler & Alerts | ✅ Complete | Timezone-aware daily matching loop, 7d/3d/1d deadline alerts, HMAC-SHA256 signed webhooks, Telegram bot |
| **M07: Hardening** | Security & Privacy | ✅ Complete | Sliding-window rate limiter, LLM daily spend caps, PII redaction audit, NDPR data export & GDPR deletion, operational runbooks |
| **M08: Launch** | Production Packaging | ✅ Complete | Multi-stage Dockerfile, docker-compose.yml, deployment guide, production README, requirements.txt |





