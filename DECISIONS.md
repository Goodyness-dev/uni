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
