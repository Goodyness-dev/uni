# 04_ARCHITECTURE.md

The single source of truth for structure. If anything here changes, make a commit with the prefix `contract:` and tell the other developer.

## 1. Stack (fixed, do not substitute)

1. Backend: Python 3.11 or 3.12, FastAPI, uvicorn, Pydantic v2, the standard library `sqlite3`, `threading`, `smtplib`, `json`, `re`, `hashlib`, `base64`.
2. Libraries beyond the standard library (exactly these, nothing else): `fastapi`, `uvicorn`, `pydantic`, `openai`, `neatlogs`, `httpx`, `pypdf`, `reportlab`, `jinja2`, `pytest`.
3. Frontend: Next.js (app router), TypeScript strict, Tailwind CSS. No component library, no state library. React hooks only.
4. LLM: the `openai` SDK for both providers. Primary is Gemini through its OpenAI compatible endpoint. Fallback is a second provider through the same SDK. Both clients are wrapped with `neatlogs.wrap`. If the primary fails the Gemini test in `03_TOOLS_SETUP.md` section 4, swap only the primary client to the Google GenAI SDK, keeping the same `call_llm` interface.
5. Notifications: Telegram Bot API with `httpx`. Email: `smtplib` with Gmail.
6. No Docker, no queue server, no database server, no agent framework, no Playwright.
7. File uploads: NO multipart. The CV PDF is sent as a base64 string inside a JSON body (see `06_API_CONTRACT.md`). This removes an extra dependency.
8. Environment loading: write a small loader in `config.py` that reads `backend/.env` line by line (`KEY=value`, skip blank lines and lines that start with a hash) and sets `os.environ` if the key is not already set. Do not add a dotenv package.

## 2. Run commands

Backend (from `backend/`): create a virtual environment named `.venv` with Python's venv module and activate it, install the packages in section 3 with `pip install` followed by the package names, then start the server with `python run_server.py`. The file `run_server.py` contains a call to `uvicorn.run` with the app path `app.main:app`, host `127.0.0.1`, port 8000 and reload enabled.
Frontend (from `frontend/`): install then `npm run dev` (port 3000).
Demo portal: served by the same FastAPI app under `/portal`.
Quick check (from `backend/`): `python scripts/quick_check.py`.
Pipeline CLI (from `backend/`): `python scripts/run_pipeline.py` with arguments described in `07_AGENTS_SPEC.md` section 12.

## 3. requirements.txt (exact content)

```
fastapi
uvicorn
pydantic
openai
neatlogs
httpx
pypdf
reportlab
jinja2
pytest
```
Do not pin versions unless something breaks. Do not add packages without asking. Install by listing the package names after `pip install` (this avoids needing any option flags).

## 4. Folder structure (create exactly this)

```
repo root
  README.md
  AGENTS.md                       (rules for Antigravity, content in 12_ANTIGRAVITY_RULES.md)
  .gitignore
  .env.example
  docs/                           (the pack files, copied here)
    evidence/                     (run_A.json, run_B.json, improvement_log.md, screenshots)
  .agent or .agents/              (rules and workflows, see 12_ANTIGRAVITY_RULES.md)
  backend/
    requirements.txt
    run_server.py                 (starts uvicorn, see section 2)
    pytest.ini                    (content: [pytest] then pythonpath = .)
    app/
      __init__.py
      main.py                     (FastAPI app, lifespan, CORS, router includes)
      config.py                   (env loader and settings)
      models.py                   (all Pydantic models, see 05_DATA_MODELS.md)
      db.py                       (sqlite connection helpers, schema, CRUD helpers)
      tracing.py                  (neatlogs init and span helpers)
      llm.py                      (call_llm, the only place that touches an LLM SDK)
      prompts.py                  (all prompt constants with versions)
      schemas.py                  (Pydantic output schemas for LLM calls, see 08_PROMPTS.md)
      errors.py                   (error classes and RunContext)
      failure_flags.py            (injectable failures)
      sensitive.py                (strip_sensitive and category rules)
      notify.py                   (Telegram, email, notification log, callback poller)
      coordinator.py              (state machine, run loop, recovery decisions)
      agents/
        __init__.py
        intake.py  scout.py  matcher.py  researcher.py  edge_finder.py
        tailor.py  verifier.py  applier.py  packager.py
      routers/
        __init__.py
        health.py  profile.py  runs.py  matches.py  applications.py  gaps.py  flags.py
      portal/
        __init__.py
        routes.py
        templates/                (HTML templates, owned by Ayo)
    data/
      listings.json
      dossier_cache/              (one JSON per listing id)
      synthetic/                  (persona files)
      vault/                      (real vault files, gitignored)
      packages/                   (generated packages, gitignored)
      app.db                      (gitignored)
    scripts/
      quick_check.py  seed_persona.py  run_pipeline.py  eval_runs.py
    tests/
      conftest.py  test_*.py
  frontend/
    app/  components/  lib/  mocks/
```

## 5. The run lifecycle (what happens when the user presses Run agent)

1. `POST /api/runs` validates, creates a `runs` row with status `running`, starts a `threading.Thread` that calls `coordinator.execute_run(run_id)`, and returns 202.
2. `execute_run` is decorated as the WORKFLOW span. It loads facts and preferences from the database.
3. Scout loads listings. Matcher creates one `applications` row per listing (status `found` then `matched` or `skipped`).
4. The Coordinator sorts matched applications by fit score descending, then nearest deadline, then takes `top_n` for deep processing. Others stay `matched`.
5. For each deep application, in order: research, edges, tailor, verify, package, apply. Each step is idempotent (skips when its output already exists in the row).
6. Each step runs inside `run_step(app_id, step_name, function)` which handles retries, fallbacks, recovery decisions, events and neatlogs attributes (section 7).
7. At the end the run metrics are computed and stored, `finished_at` is set, status becomes `completed` (or `failed` only when the run itself crashed). A failure in one application never fails the run.
8. Telegram messages are sent through `notify.send_event(app_id, kind, ...)` at the transitions listed in `05_DATA_MODELS.md` section 7.

## 6. Application state machine

Statuses: `found`, `matched`, `skipped`, `researched`, `edges_selected`, `tailored`, `verified`, `ready`, `submitting`, `awaiting_user`, `submitted`, `prepared`, `unconfirmed`, `failed`.

Allowed transitions (enforce in `db.set_status`, raise `ValueError` otherwise):
1. `found` to `matched` or `skipped`.
2. `matched` to `researched`.
3. `researched` to `edges_selected`.
4. `edges_selected` to `tailored`.
5. `tailored` to `verified`.
6. `verified` to `ready`.
7. `ready` to `submitting`, `prepared`.
8. `submitting` to `submitted`, `awaiting_user`, `unconfirmed`, `failed`, `prepared`.
9. `awaiting_user` to `submitting`.
10. `unconfirmed` to `submitting`.
11. Any status to `failed` is allowed.

Rule: `submitted` is set ONLY after a confirmation was read back from the portal or SMTP accepted the message. Otherwise the status is `submitting`, `awaiting_user`, `unconfirmed` or `prepared`.

## 7. run_step and recovery decisions (Coordinator core)

`run_step(ctx, step_name, fn, fallback=None)` behaves like this:
1. Check idempotency: if the step's output already exists, return it and log nothing.
2. Attempt loop up to 3 attempts with sleeps of 1, 2 and 4 seconds (use 0 in tests via a setting).
3. On a retryable error (`RateLimitError`, `TimeoutError_`, `PortalError` with 5xx, `BadJSONError`) record a `retry` event and continue.
4. Before switching to a fallback, record a recovery decision (section 8).
5. If the attempts are exhausted and a `fallback` function exists, call it inside a `recovery_decision` span, record the decision, and return its result. If there is no fallback or it fails, set the application to `failed` with `failure_reason` and return None.
6. Errors that are NOT retryable (`BlockerDetected`, validation errors) skip the retry loop and go straight to their handling.

## 8. Recovery decisions (neatlogs depth)

A recovery decision is a record with: `trigger`, `options` (list of strings), `chosen`, `reason` (one sentence), `outcome`. For each decision do ALL of these:
1. Open a neatlogs span through `tracing.recovery_decision(trigger, options)` and set the attributes `recovery.trigger`, `recovery.options`, `recovery.chosen`, `recovery.reason`, `recovery.outcome`.
2. Write an `events` row of type `recovery_decision` with the same fields in `data`.
3. Write a neatlogs log line with the same text.

Deterministic rules choose the recovery (table in `10_FAILURES_AND_RECOVERY.md` section 2). The stretch version where an LLM chooses from a whitelist is in the same file, section 5.

## 9. Concurrency and database rules

1. SQLite file at `backend/data/app.db`. Open a NEW connection for every function call in `db.py` (`sqlite3.connect(path, timeout=10)`), set `row_factory = sqlite3.Row`, run `PRAGMA journal_mode=WAL` once at schema creation, and always close the connection.
2. All writes use short transactions with `with conn:` blocks.
3. JSON columns are stored with `json.dumps` and read with `json.loads`.
4. The run thread and the Telegram poller thread both write events. Never share a connection between threads.
5. On startup, mark any run with status `running` as `interrupted` and write an event.

## 10. Configuration (`config.py` fields)

Read from the environment (names exact):
1. `LLM_PRIMARY_BASE_URL`, `LLM_PRIMARY_API_KEY`, `LLM_PRIMARY_MODEL`
2. `LLM_FALLBACK_BASE_URL`, `LLM_FALLBACK_API_KEY`, `LLM_FALLBACK_MODEL`
3. `PRICE_PRIMARY_IN_PER_MTOK`, `PRICE_PRIMARY_OUT_PER_MTOK`, `PRICE_FALLBACK_IN_PER_MTOK`, `PRICE_FALLBACK_OUT_PER_MTOK` (floats, default 0.30 and 2.50 as placeholders, check provider price pages)
4. `NEATLOGS_API_KEY`, `NEATLOGS_ENDPOINT` (optional, for EU), `NEATLOGS_DASHBOARD_URL` (default https://app.neatlogs.com)
5. `CRUSTDATA_API_KEY` (optional)
6. `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
7. `SMTP_HOST` (default smtp.gmail.com), `SMTP_PORT` (default 587), `SMTP_USER`, `SMTP_APP_PASSWORD`, `DEMO_INBOX_EMAIL`
8. `PUBLIC_BASE_URL` (default http://localhost:8000), `FRONTEND_BASE_URL` (default http://localhost:3000)
9. `LIVE_RESEARCH` (default false), `RETRY_SLEEP_SECONDS` (default 1, tests set 0), `DEMO_MODE` (default true), `TODAY_OVERRIDE` (optional, format `YYYY/MM/DD`, makes deadline checks deterministic for demos and tests)

Attribute names on the settings object are the lowercase environment variable names (for example `settings.llm_primary_base_url`, `settings.neatlogs_api_key`, `settings.today_override`). Booleans and numbers are converted from strings (true or false, integers, floats). A settings object `settings` is created once at import. Missing optional values are allowed. The health endpoint reports `configured` or `missing` for each group.

## 11. Security and privacy rules

1. Secrets only in `backend/.env` and `frontend/.env.local`. Both are gitignored.
2. The real Vault files live in `backend/data/vault/` (gitignored). The repo ships only the synthetic persona.
3. `sensitive.strip_sensitive` runs before EVERY LLM call that includes facts.
4. Fetched web text is DATA, never instructions. Wrap it in delimiters and never let it change tool choices.
5. Do not log full CV or essay text for real users. Log ids, counts and lengths. For the synthetic persona full capture is fine.
6. The Researcher only reads public institutional pages. No social media, no personal contact details.
7. The Applier never submits to any URL other than our own portal paths and our own inbox.

## 12. Error classes (define in `app/errors.py` or at the top of `llm.py`)

Define these exception classes: `LLMError`, `RateLimitError` (subclass of LLMError), `ModelNotFoundError` (subclass of LLMError), `BadJSONError` (subclass of LLMError), `TimeoutError_` (subclass of LLMError, note the trailing underscore to avoid the built in name), `PortalError` (has `status_code`), `BlockerDetected` (has `kind`), `SmtpError`, `ResearchError`. Put them in `backend/app/errors.py` and import from there everywhere.
