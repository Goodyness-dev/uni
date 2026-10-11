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

## Getting Started

### Production Setup (Under 10 Minutes)
```bash
# 1. Clone repository and install dependencies
git clone https://github.com/Goodyness-dev/uni.git
cd uni
pip install fastapi uvicorn pydantic pydantic-settings sqlalchemy alembic aiosqlite asyncpg redis httpx cryptography neatlogs pytest greenlet

# 2. Run database migrations
alembic upgrade head

# 3. Seed demo scholarship catalog into database
python scripts/import_catalog.py

# 4. Run automated test suite
pytest tests/test_foundation.py

# 5. Boot the production API server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
# Access Swagger UI at http://localhost:8000/docs
# Access Health check at http://localhost:8000/health
```

### Hackathon Demo Setup (Legacy)
```bash
cd backend
python -m venv .venv
# Activate virtual environment
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate

pip install -r requirements.txt

# Start demo backend server
python run_server.py
```

### Frontend Setup
```bash
cd frontend
npm install
npm run dev
# Open http://localhost:3000
```

### Running Pipeline & Evaluation CLI
```bash
# Execute Mode B pipeline with Neatlogs tracing
python backend/scripts/run_pipeline.py B 2 "demo,evidence"

# Run automated evaluation suites
python backend/scripts/eval_runs.py --suite eval_v2 --mode B --runs 3

# Seed database to demo state
python backend/scripts/seed_persona.py
```

---

## Honest Limitations

1. **No Automated Real Portal Submissions**: ScholarPilot never attempts to scrape or bypass live university authentication systems. All automated submissions target either the local demo portal or direct committee email. For external sites, ScholarPilot generates a complete, verified application pack (`cv.pdf`, `essay.txt`, and briefing notes).
2. **CAPTCHA Stance**: ScholarPilot never attempts to bypass CAPTCHAs. When encountered, it immediately stops and triggers an interactive Telegram handoff to the applicant.
3. **Synthetic Persona**: All demo applicant profiles and transcripts in this repository are synthetic to respect privacy.
4. **Human Review Requirement**: While Mode B verification eliminates unsupported claims, applicants must perform final human review before submitting scholarship materials.

---

## Team

- **Memeshi**: Agent architecture, backend pipelines, Neatlogs tracing, failure recovery, verification engine.
- **Ayo**: UI/UX design, Next.js frontend, interactive demo portal, Telegram integration.
