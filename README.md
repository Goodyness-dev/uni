# ScholarPilot

**ScholarPilot** is an autonomous, verification-first scholarship application agent that finds scholarships you qualify for, researches the university and department priorities, selects your grounded evidence from a verified profile vault, drafts tailored CVs and essays, proves every single claim with self-challenging guardrails, and safely submits or hands off to human applicants.

Built in 48 hours for the **neatHack** AI agent hackathon (October 10 to 12, 2026) by Memeshi (agents, backend, and observability) and Ayo (design and frontend). All code in this repository was written during the hackathon under Google Antigravity pair programming and Entire checkpoint tracking.

- **GitHub Repository**: [https://github.com/Goodyness-dev/uni.git](https://github.com/Goodyness-dev/uni.git)
- **Demo Video**: [https://youtu.be/scholarpilot-demo](https://youtu.be/scholarpilot-demo)
- **Business Plan (cfo.ai, read-only)**: [https://app.cfo.ai/p/scholarpilot-business-plan](https://app.cfo.ai/p/scholarpilot-business-plan)
- **Full Evidence Dossier**: [EVIDENCE.md](file:///EVIDENCE.md) and [`docs/evidence/`](file:///docs/evidence/)

---

## What It Does

1. **Intake & Profile Vault**: Ingests your CV, transcripts, preferences, and private Profile Vault facts (volunteering, leadership, hardship, research milestones). Extracts grounded, typed facts without hallucination.
2. **Scout & Matcher**: Filters scholarships through deterministic hard eligibility criteria (GPA, major, residency, deadlines) and scores contextual fit.
3. **Researcher**: Researches the institution and scholarship priorities. Every dossier fact requires a real source URL and verified text snippet; cleanses adversarial prompt injections automatically.
4. **Edge Finder**: Compares your personal vault facts against university priorities to discover authentic competitive edges.
5. **Tailor**: Drafts tailored CV summaries, bullet points, and essay responses where every sentence explicitly cites source fact IDs.
6. **Verifier (Self-Healing Guardrails)**:
   - Audits each claim against ground-truth facts.
   - Launches an adversarial Challenger LLM to disprove generated claims.
   - In Mode B, runs up to 2 targeted revision passes. If any claim remains unverified, a deterministic removal fallback excises the sentence, marking it as removed in the audit trail.
   - Result: **Reduces unsupported/hallucinated claims from 16 down to exactly 0 (100% reduction)**.
7. **Safe Submissions & Human Handoff**: Dispatches verified applications via demo portals or committee emails. When security walls or CAPTCHAs are detected, it pauses execution and sends an interactive Telegram handoff to the applicant with `Done` and `Open` actions, resuming only after applicant verification.

---

## Sponsor Tools Integration

### 1. Neatlogs (Traces, Guardrails, & Continuous Improvement)
- **Comprehensive Tracing Hierarchy**: Every agent execution, LLM call, and tool invocation is traced with UPPERCASE spans: `WORKFLOW`, `AGENT`, `CHAIN`, `TOOL`, `RETRIEVER`, and `GUARDRAIL`.
- **GUARDRAIL Spans**: The Verifier creates typed `GUARDRAIL` spans reporting `passed=True` (compliant) or `passed=False` (unsupported/hallucinated).
- **Run A vs. Run B Improvement Loop**:
  - **Run A (Advisory mode)**: 16 claims total, 16 unsupported claims in final output.
  - **Run B (Self-healing mode)**: 16 claims total, **0 unsupported claims in final output (-100%)**.
  - Documented in [`docs/evidence/improvement_log.md`](file:///docs/evidence/improvement_log.md) and [`docs/evidence/comparison_table.md`](file:///docs/evidence/comparison_table.md).
- **Recovery Decision Spans**: Failures (rate limits, malformed JSON, portal 500s, CAPTCHAs, unreachable research, SMTP errors) open `recovery_decision` CHAIN spans recording triggers, alternatives, chosen remedies, and rationales.
- **Trace Deep-Linking**: Every run and application exposes a dynamic `trace_url` linking straight to the Neatlogs dashboard.
- **15 Production Detections**: Configured detection rules for cost spikes, latency anomalies, retry storms, prompt injection, and PII leakage.

### 2. Entire (Agent Checkpointing)
- Entire tracking was initialized before the very first commit.
- All 26 commits on `main` follow structured commit conventions (`<type>(<area>): <what> [<task id>]`) with explicit Neatlogs observability summaries.
- Provides cryptographic, tamper-evident checkpoints of agent trajectory and human-in-the-loop pair programming sessions.

### 3. cfo.ai (Financial Modeling & Unit Economics)
- **Data-Driven Unit Economics**: Fed directly by Neatlogs token measurements:
  - Tokens per application: ~12,500 input, ~2,200 output.
  - LLM Cost per tailored & verified application: **\$0.0025 USD** (~₦4.00).
- **Pricing & Margins**:
  - Pay-Per-Application Lead Tier: **\$4.99 USD** (~99.9% gross margin).
  - Season Pass: **\$19.99 USD** (10 verified applications).
- **Runway & Break-even**: Modeled across Conservative, Base, and Growth scenarios in cfo.ai Ari. Break-even achieved in Month 1–2 with positive cash flow. Full write-up in [`docs/evidence/business_plan.md`](file:///docs/evidence/business_plan.md).

---

## Architecture

```
User CV / Transcript / Vault
            │
            ▼
       [ Intake ] ──────► Facts Database (SQLite)
            │
            ▼
    [ Scout & Matcher ] ───► Eligible Opportunities
            │
            ▼
      [ Researcher ] ────► Sourced Dossiers & Anti-Injection
            │
            ▼
     [ Edge Finder ] ────► Grounded Personal Edges
            │
            ▼
        [ Tailor ] ──────► Sourced Drafts (CV + Essay)
            │
            ▼
       [ Verifier ] ◄────► [ Adversarial Challenger ]
            │ (Mode B Revisions & Deterministic Fallback)
            ▼
    100% Grounded Application Package (0 Unsupported Claims)
            │
   ┌────────┴────────┐
   ▼                 ▼
[ Applier ]    [ Packager ] ──► PDF CV + Essay Bundle
 (Portal/Email)      │
   │                 ▼
   └──────────► [ Human Handoff ] ──► Telegram Bot Alerts
```

---

## Production Architecture & Engineering

ScholarPilot has evolved from its initial 48-hour hackathon prototype into a hardened, production-grade autonomous platform:

### 1. Multi-Tenant Relational Foundation (PostgreSQL 16 & SQLAlchemy 2.0 Async)
- **11 System-of-Record Models**: `User`, `Profile`, `Document`, `Scholarship`, `Match`, `Application`, `ApplicationEvent`, `Draft`, `Job`, `ApiKey`, `Webhook`.
- **Append-Only Auditing**: Every state change, user intervention, and external submission is permanently recorded in `application_events`.
- **Alembic Migrations**: Fully version-controlled relational schema with production indexes on deadlines, compound `(user_id, status)` queries, and scholarship IDs.

### 2. 12-State Application Lifecycle & Autonomy Modes
Applications progress through a strictly validated directed state machine:
```
discovered ──► matched ──► researching ──► drafting ──► ready_for_review ──► approved ──► submitting ──► submitted
                                              │                                               ▲     │
                                              │ (autopilot mode)                              │     ▼
                                              └───────────────────────────────────────────────┴─► needs_human
                                                                                                    (CAPTCHA/MFA)
```
- **Autopilot Mode**: The agent autonomously discovers, researches, drafts, and submits applications matching student preferences.
- **Review Mode**: Submissions are strictly held in `ready_for_review` until the student explicitly approves the draft materials via `POST /v1/applications/{id}/approve`.
- **Emergency Kill Switch**: Global runtime circuit breaker (`KILL_SWITCH_ACTIVE=true`) that halts all active submissions instantaneously.

### 3. Agent Task Queue & Idempotent Submitter
- **Queue Worker Harness**: Background jobs executed via asynchronous Redis task broker with stored attempt counts and dead-letter recovery.
- **Idempotency Guarantee**: Submitter checks application confirmation status prior to opening browser sessions; duplicate runs return `already_submitted` with 0 duplicate submissions.
- **Human Blocker Handoff**: Strict zero-bypass policy on CAPTCHAs, MFA prompts, login walls, and unexpected application fees; automatically captures step screenshots and transitions state to `needs_human`.

### 4. Autonomous Daily Scheduler & Deadline Reminders
- **Daily Discovery Loop**: Scheduled cycle per student timezone executing match evaluations and dispatching new opportunities.
- **Proactive Deadline Buckets**: Evaluates catalog deadlines and fires high-priority alerts at:
  - **7 Days Remaining (`7d`)**
  - **3 Days Remaining (`3d`)**
  - **1 Day Remaining (`1d`)**
- **Notification Channels**: Clean Markdown briefings dispatched via Telegram bot and HMAC-SHA256 signed event webhooks.

### 5. Production Hardening & Privacy Protections
- **Sliding-Window Rate Limiter**: Token-bucket abuse protection per API key and client IP.
- **LLM Cost Caps**: Daily per-user spend cap (\$1.00) and global spend cap (\$50.00) with automatic model fallback and circuit breaking.
- **Automated PII Redaction**: Structured JSON logging scrubs student emails, phone numbers, national IDs, and raw essay text before writing logs.
- **NDPR & GDPR Compliance**: Student data archive export (`GET /v1/account/export`) and permanent data erasure under the Right to be Forgotten (`DELETE /v1/account`).

---

## Production API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` & `/ready` | Liveness and readiness system probes |
| `POST` | `/v1/auth/keys` | Generate new developer API key (`sp_live_...`) |
| `DELETE` | `/v1/auth/keys/{id}` | Revoke developer API key |
| `GET` | `/v1/profile` | Retrieve verified Profile Vault facts |
| `PUT` | `/v1/profile` | Update Profile Vault and recalculate completeness score |
| `POST` | `/v1/documents` | Upload verified academic transcript / CV metadata |
| `GET` | `/v1/scholarships` | Query scholarship catalog with multi-attribute filters |
| `GET` | `/v1/matches` | Retrieve ranked opportunities with plain-language fit reasons |
| `POST` | `/v1/matches/refresh` | Trigger real-time eligibility and ranking sweep |
| `GET` | `/v1/applications` | List active student applications |
| `POST` | `/v1/applications` | Initialize application for target scholarship |
| `POST` | `/v1/applications/{id}/approve` | Approve drafted materials in Review mode |
| `POST` | `/v1/applications/{id}/resume` | Resume submission following human blocker resolution |
| `POST` | `/v1/applications/{id}/withdraw` | Cancel application |
| `GET` | `/v1/settings` & `PUT` | Configure user autonomy mode (`autopilot` vs. `review`) |
| `GET` | `/v1/account/export` | Download complete student data archive (NDPR/GDPR) |
| `DELETE` | `/v1/account` | Permanently purge personal data and Profile Vault |

---

## Getting Started

### Production Deployment (Docker Compose)
```bash
# 1. Clone repository
git clone https://github.com/Goodyness-dev/uni.git
cd uni

# 2. Build and launch Postgres, Redis, API, and Worker
docker compose up -d --build

# 3. Run database migrations and seed catalog
docker compose exec api alembic upgrade head
docker compose exec api python scripts/import_catalog.py

# 4. Verify system health
curl http://localhost:8000/ready
```

### Local Development & Testing
```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run all 30 automated acceptance tests
pytest tests/ -v

# 3. Launch local development server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## Team

- **Memeshi**: Agent architecture, backend pipelines, Neatlogs tracing, failure recovery, verification engine.
- **Ayo**: UI/UX design, Next.js frontend, interactive demo portal, Telegram integration.

