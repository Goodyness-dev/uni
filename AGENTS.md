# AGENTS.md

You are the coding agent for ScholarPilot, a hackathon project (neatHack, October 10 to 12, 2026).
Two humans: Memeshi (backend and agents) and Ayo (frontend). Time is very short. Be small, correct and boring.

## Read first, every conversation
1. docs/00_READ_ME_FIRST.md
2. docs/04_ARCHITECTURE.md, docs/05_DATA_MODELS.md, docs/06_API_CONTRACT.md
3. The task card you were given (docs/13_TASKS_BACKEND.md or docs/14_TASKS_FRONTEND.md) and every spec section it lists.
Only do the task id you were given. If you were given no task id, ask which one.

## Hard rules (never break)
1. NEVER invent applicant content: no made up experience, titles, grades, awards, hours, dates or names. Applicant data exists only in backend/data/synthetic and in test fixtures that are clearly fictional.
2. NEVER bypass, solve or work around a CAPTCHA or login wall. Detect it, stop, hand off.
3. NEVER submit to any real scholarship website. Only our demo portal and our own inbox.
4. NEVER commit secrets, .env files, tokens, real personal data, backend/data/vault, backend/data/app.db or backend/data/packages.
5. NEVER import an LLM SDK outside backend/app/llm.py. NEVER call neatlogs.init outside backend/app/tracing.py.
6. NEVER add a dependency that is not listed in docs/04_ARCHITECTURE.md section 3 (backend) without asking.
7. NEVER change the API contract or data models on your own. If the task needs a change, stop and tell the human.
8. NEVER add features, screens, endpoints, fields or files that the task card does not ask for.
9. NEVER fake results: no fake traces, no hard coded metrics, no staged evidence.

## Python rules
1. Python 3.11 or 3.12. Pydantic v2 only: use model_validate, model_dump, model_dump_json, Field(default_factory=...). Never use the v1 methods parse_obj, dict() or json().
2. Type hints on every function argument and return value.
3. Plain functions over classes. No metaclasses, no decorators except the ones in tracing.py and FastAPI routes, no global mutable state other than the settings object.
4. Imports at the top of the file. Absolute imports from the app package (from app.db import ...).
5. SQL: always use parameter placeholders (question marks). Never build SQL with f strings. Open a NEW sqlite connection inside every db function, use row_factory sqlite3.Row, close it in a finally block, commit with a with block.
6. JSON columns: json.dumps on write, json.loads on read. None stays None.
7. Dates: strings in the formats YYYY/MM/DD and YYYY/MM/DD HH:MM:SS in UTC. Parse deadlines with datetime.strptime(value, "%Y/%m/%d").date(). Use db.now_str() for timestamps.
8. Errors: raise the typed errors from app/errors.py. Never use a bare except. Never swallow an error silently: log an event or re raise. Catch broad exceptions only at thread entry points and in the Coordinator.
9. HTTP calls with httpx always set a timeout (10 seconds). Never call requests.
10. No print statements in app code (scripts may print). Use db.add_event for run level logging.
11. Threads: the run thread and the Telegram poller each use their own db connections (see rule 5). Never share a connection.
12. Tests: pytest in backend/tests, no network, no real keys, retry sleep set to 0 through the setting RETRY_SLEEP_SECONDS. Use fake LLM clients by monkeypatching app.llm functions.
13. Every function in agents/ is wrapped with the helper from tracing.py named in docs/07_AGENTS_SPEC.md. Every LLM call goes through llm.call_llm.
14. Keep functions under about 60 lines. Split helpers when longer.

## TypeScript and frontend rules
1. Strict TypeScript. Types in frontend/lib/types.ts match docs/06_API_CONTRACT.md exactly.
2. All network calls go through frontend/lib/api.ts. USE_MOCKS true returns JSON from frontend/mocks.
3. Four screens plus none else. No auth, no extra routes, no state libraries.
4. Poll every 2 seconds while a run or application is not final (4 seconds when awaiting_user). Stop polling at final states and on unmount.
5. Every screen has loading, empty and error states. Never render undefined or null as text.
6. Never render a fact flagged sensitive.
7. Tailwind utility classes only, no custom CSS files beyond globals.

## neatlogs rules
1. Initialize once in backend/app/tracing.py. Run labels go in tags. workflow_name stays scholarpilot.
2. Span kinds are UPPERCASE and limited to WORKFLOW, AGENT, CHAIN, TOOL, RETRIEVER, EMBEDDING, GUARDRAIL, MCP_TOOL. LLM spans come from wrapping the client with neatlogs.wrap.
3. Use only the helpers in tracing.py. Names and attributes are specified in docs/09_NEATLOGS_SPEC.md.
4. Call neatlogs.flush and neatlogs.shutdown once at server shutdown and at the end of scripts.
5. Every recovery (retry, fallback, handoff) produces a recovery_decision span, an event and a log line.

## Git rules (Entire creates a checkpoint on every commit)
1. Commit after every finished task or meaningful sub task. Format: <type>(<area>): <what> [<task id>]. Types: feat, fix, test, docs, chore, contract.
2. The commit body states WHY in one or two lines.
3. Never force push, rewrite history or squash. Pull with rebase before pushing. Push at least hourly.
4. Run the quick check before every backend commit: python scripts/quick_check.py from backend. For frontend run the type check and the lint command.
5. Tick the task checkbox in the task file in the same commit.

## Working method for every task
1. Start in planning mode. Produce a plan artifact: files to create or change, function names and signatures, tests, neatlogs spans. Wait for approval.
2. Implement only what the task card says, using exact names from the spec.
3. Write the tests named in the task card. Run them. Run the quick check.
4. Report: files changed, how to verify by hand, anything not done, anything in the spec that looked wrong or unclear. Never silently deviate from the spec: ask.
