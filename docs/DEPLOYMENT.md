# ScholarPilot Production Deployment Guide

This guide describes how to deploy, configure, and operate the ScholarPilot production platform.

---

## 1. System Architecture & Topology

ScholarPilot is an autonomous scholarship application system designed for Nigerian and African students. In production, it operates across four coordinated services:

```
                  +-----------------------------------+
                  |         Internet / Client         |
                  +-----------------+-----------------+
                                    | HTTPS
                                    v
+-------------------------------------------------------------------------+
| Reverse Proxy (Caddy / Nginx / Cloudflare)                              |
+-----------------------------------+-------------------------------------+
                                    |
                                    v
+-----------------------------------+-------------------------------------+
| api Service (FastAPI + Uvicorn)                                         |
| - REST API v1 (/auth, /profile, /documents, /scholarships, /matches)    |
| - State Machine & Mode Enforcement (Autopilot vs. Review)               |
| - Neatlogs Observability Gateway                                        |
+-------------------+---------------------------------+-------------------+
                    |                                 |
                    v                                 v
+-------------------+-------------+     +-------------+-------------------+
| db Service (PostgreSQL 16)      |     | redis Service (Redis 7)         |
| - System of Record              |     | - Job Queue Broker              |
| - 11 Relational Schema Tables   |     | - Distributed Locks (TTL)       |
| - Append-only Event Timeline    |     | - Token Bucket Rate Limiting    |
+---------------------------------+     +-------------+-------------------+
                                                      |
                                                      v
                                        +-------------+-------------------+
                                        | worker Service                  |
                                        | - Matcher & Researcher Agents   |
                                        | - Drafter (Grounding & Limits)  |
                                        | - Submitter (Playwright Runner) |
                                        | - Daily Autonomous Scheduler    |
                                        +---------------------------------+
```

---

## 2. Prerequisites

- **Host Operating System**: Linux (Ubuntu 22.04 LTS / Debian 12 recommended) or Windows Server with WSL2.
- **Docker Engine**: Version 24.0 or higher.
- **Docker Compose**: Version 2.20 or higher.
- **Compute**: Minimum 2 vCPU, 4GB RAM (8GB RAM recommended for headless Playwright execution).
- **Outbound Network**: HTTP/HTTPS access to LLM gateway providers and scholarship portal domains.

---

## 3. Environment Configuration

Create a production `.env` file in the project root:

```bash
# Environment & Runtime
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO

# Database Connection (Async PostgreSQL with asyncpg)
DATABASE_URL=postgresql+asyncpg://scholarpilot:scholarpilot_secret@db:5432/scholarpilot_db
REDIS_URL=redis://redis:6379/0

# Credential Encryption (32-byte URL-safe base64 Fernet key)
ENCRYPTION_KEY=e3w8oG2Z5mY6pT9vQ1rU4xN7bK0jH3fD2sA5lP8oI1u=
SECRET_KEY=generate_with_openssl_rand_hex_32

# Model Gateway & Spend Caps
DEFAULT_LLM_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_api_key_here
USER_DAILY_SPEND_CAP_USD=1.00
GLOBAL_DAILY_SPEND_CAP_USD=50.00

# Emergency Stop
KILL_SWITCH_ACTIVE=false

# Notifications (Optional)
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
```

---

## 4. Bootstrapping the Services

### Step 1: Build and Launch Containers
```bash
docker compose up -d --build
```

### Step 2: Verify Service Health
```bash
docker compose ps
```
Both `scholarpilot-db` and `scholarpilot-redis` should report `healthy`, and `scholarpilot-api` should be active on port `8000`.

### Step 3: Run Database Migrations
```bash
docker compose exec api alembic upgrade head
```

### Step 4: Import Catalog Listings
```bash
docker compose exec api python scripts/import_catalog.py
```

### Step 5: Test Health Probes
```bash
curl http://localhost:8000/health
# Response: {"status":"healthy","environment":"production"}

curl http://localhost:8000/ready
# Response: {"status":"ready","database":"connected","redis":"available","catalog_scholarships":5}
```

---

## 5. Reverse Proxy & SSL Termination

Deploy Nginx or Caddy in front of the API on port 8000. Example Caddyfile:

```caddy
api.scholarpilot.africa {
    reverse_proxy localhost:8000 {
        header_up X-Forwarded-Proto {scheme}
        header_up X-Real-IP {remote}
    }
}
```

---

## 6. Observability with Neatlogs

ScholarPilot instruments every stage of the scholarship lifecycle through Neatlogs:
- **Spans**: `WORKFLOW`, `AGENT`, `CHAIN`, `TOOL`, `GUARDRAIL`.
- **Workflow Name**: `scholarpilot`.
- **Tracing Guarantees**:
  - LLM token accounting recorded per user ID and job ID.
  - Every recovery decision (retry, fallback, handoff) records a recovery span.
  - PII scrubbing occurs prior to logging to ensure zero student privacy leakage.

---

## 7. Backup and Recovery

### PostgreSQL Daily Automated Dump
```bash
docker compose exec -t db pg_dump -U scholarpilot -d scholarpilot_db | gzip > /backups/db_$(date +%Y%m%d).sql.gz
```

### Restore from Backup
```bash
gunzip < /backups/db_YYYYMMDD.sql.gz | docker compose exec -T db psql -U scholarpilot -d scholarpilot_db
```
