# 06_API_CONTRACT.md

The contract between backend (Memeshi) and frontend (Ayo). Shapes use the models in `05_DATA_MODELS.md`. If anything here changes, make a `contract:` commit and tell the other person immediately.

## 1. Global rules

1. Base URL `http://localhost:8000`. CORS allows `http://localhost:3000`.
2. All request and response bodies are JSON. No multipart anywhere.
3. Dates are `YYYY/MM/DD`. Date times are `YYYY/MM/DD HH:MM:SS` in UTC.
4. Errors: HTTP status plus body `{"error": "short_code", "message": "human readable text"}`. Codes used: `bad_request` (400), `not_found` (404), `conflict` (409), `server_error` (500).
5. Polling: the frontend polls `GET /api/runs/{id}/events` and `GET /api/applications/{id}` every 2 seconds while not final. Final application statuses: `submitted`, `prepared`, `failed`, `skipped`, `unconfirmed`. `awaiting_user` is NOT final (keep polling but slower, every 4 seconds). Final run statuses: `completed`, `failed`, `interrupted`.
6. Every list response is an object with a named array, never a bare array.

## 2. Health

`GET /api/health` returns
```json
{"status": "ok", "llm_primary": "configured", "llm_fallback": "configured", "telegram": "configured", "neatlogs": "configured", "smtp": "configured", "crustdata": "missing", "demo_mode": true}
```
Values are `configured` or `missing`.

## 3. Profile

`POST /api/profile/intake` body:
```json
{
  "cv_text": "optional string",
  "cv_pdf_base64": "optional base64 string of a PDF",
  "transcript_text": "optional string",
  "preferences": {"full_name": "Tobi Adeyemi", "email": "tobi@example.com", "level": "masters", "fields": ["computer engineering"], "countries": ["UK"], "funding": "full", "start_year": 2027, "nationality": "Nigeria", "gpa": 4.3, "gpa_scale": 5.0, "sensitive_consent": false},
  "vault_sections": {"sports": "text", "volunteering": "text", "certifications": "text", "leadership": "text", "awards": "text", "projects": "text", "languages": "text", "hardships": "text", "career_goals": "text", "why_abroad": "text"},
  "vault_text": "optional free text"
}
```
At least one of `cv_text` or `cv_pdf_base64` is required, else 400 `bad_request`. Response 201:
```json
{"facts": [Fact], "counts": {"cv": 22, "transcript": 9, "vault": 31}, "warnings": ["optional message strings"]}
```
Behavior: replaces all previous facts and preferences.

`POST /api/profile/load_demo` (only when `demo_mode` is true, else 404) loads the synthetic persona files and runs the same intake. Response same as intake.

`GET /api/profile/facts` returns `{"facts": [Fact]}` plus `"preferences": Preferences or null`.
`PATCH /api/profile/facts/{fact_id}` body `{"text": "..."}` returns `Fact`. 404 if unknown.
`POST /api/profile/facts` body `{"category": "volunteering", "text": "..."}` creates a vault fact with the next `P` id, returns `Fact` (201).

## 4. Runs

`POST /api/runs` body `{"mode": "B", "top_n": 2, "live_research": false, "tags": ["optional"]}` returns 202:
```json
{"run_id": "run_20261011_001", "status": "running"}
```
409 `conflict` if another run is `running`. 400 if no facts exist.

`GET /api/runs/{run_id}` returns
```json
{"run_id": "run_20261011_001", "mode": "B", "status": "running", "started_at": "2026/10/11 09:02:11", "finished_at": null, "application_ids": ["app_1"], "metrics": null, "trace_url": null}
```
`metrics` is a `RunMetrics` when completed.

`GET /api/runs/latest` returns the most recent run in the same shape, or 404 when none exists.

`GET /api/runs/{run_id}/events?after=0` returns `{"events": [Event], "last_event_no": 41}`. `after` is exclusive. Events are ordered ascending by `event_no`.

`POST /api/runs/{run_id}/resume` returns 202 `{"run_id": "...", "status": "running"}`. Only allowed when the run is `interrupted` or `failed` (else 409).

## 5. Matches

`GET /api/matches?run_id=...` (run_id optional, default latest) returns `{"matches": [Match]}` sorted by fit score descending, with skipped ones at the end.

## 6. Applications

`GET /api/applications?run_id=...` returns `{"applications": [ApplicationSummary]}`:
```json
{"id": "app_1", "listing_id": "mock_portal_masters", "name": "Demo Portal Masters Award", "is_mock": true, "status": "awaiting_user", "channel": "portal_captcha", "fit_score": 87, "deadline": "2026/12/01", "updated_at": "2026/10/11 09:05:44"}
```

`GET /api/applications/{id}` returns
```json
{
  "id": "app_1",
  "run_id": "run_20261011_001",
  "listing": {"id": "...", "name": "...", "is_mock": true, "provider": "...", "country": "UK", "deadline": "2026/12/01", "channel": "portal_captcha", "ai_policy": "allowed", "source_url": "...", "essay_prompt": "...", "essay_word_limit": 300},
  "status": "awaiting_user",
  "fit_score": 87,
  "fit_reason": "one sentence",
  "failure_reason": null,
  "dossier": Dossier or null,
  "edges": [Edge],
  "tailored": TailoredOutput or null,
  "verification": VerificationReport or null,
  "package": {"cv_pdf_url": "/api/applications/app_1/files/cv", "essay_url": "/api/applications/app_1/files/essay", "checklist_url": "/api/applications/app_1/files/checklist"} or null,
  "handoff": {"reason": "captcha", "portal_url": "http://localhost:8000/portal/draft/abc123", "instructions": "text"} or null,
  "submission": {"confirmed": false, "confirmation_code": null, "channel": "portal_captcha", "at": null},
  "notifications": [{"at": "2026/10/11 09:05:44", "text": "...", "sent": true}],
  "timeline": [Event],
  "trace_url": "string or null",
  "metrics": null
}
```
All fields are always present. Unavailable data is `null` or an empty list. `edges` includes unselected edges with `selected` false (the UI shows only selected ones in the main list).

`GET /api/applications/{id}/files/{kind}` where kind is `cv`, `essay` or `checklist` returns the file (PDF for `cv`, plain text for the others) with the right content type. 404 if not built yet.

`POST /api/applications/{id}/handoff/done` returns 202 `{"status": "submitting"}`. 409 if the application is not `awaiting_user`. The backend runs the resume logic in a background thread.

## 7. Gaps

`GET /api/gaps?run_id=...` returns `{"gaps": [{"id": "G1", "application_id": "app_1", "criterion": "leadership", "question": "...", "answered": false}]}`.
`POST /api/gaps/{id}/answer` body `{"text": "..."}` creates a vault fact, marks the gap answered, returns `{"fact": Fact}`. It never blocks the pipeline and does not trigger a rerun in the hackathon version.

## 8. Failure flags (testing and evidence only)

`GET /api/failure_flags` returns `{"flags": {"llm_429": false, "bad_json": false, "portal_500": false, "captcha_wall": false, "research_down": false, "smtp_fail": false, "injection_page": false}}`.
`POST /api/failure_flags` body is a partial `{"flags": {"captcha_wall": true}}` and returns the full object. Enabling a flag with a count: body `{"flags": {"llm_429": true}, "counts": {"llm_429": 2}}`. Counted flags decrement on use and switch themselves off at zero. `captcha_wall` and `injection_page` are not counted (stay on until switched off).

## 9. Demo portal (served by the backend, not under `/api`)

1. `GET /portal/about/{listing_id}` HTML page with the fictional school information (the Researcher reads it).
2. `GET /portal/apply/{listing_id}` HTML application form. If `captcha_wall` is on, or the listing channel is `portal_captcha`, the page contains the element `id="captcha_challenge"`.
3. `POST /portal/api/draft` body `{"listing_id": "...", "idempotency_key": "app_1", "fields": {"full_name": "...", "email": "...", "summary": "...", "essay": "..."}}` returns 201 `{"draft_id": "abc123", "draft_url": "http://localhost:8000/portal/draft/abc123"}`. The same idempotency key returns the same draft.
4. `GET /portal/draft/{draft_id}` HTML page with the prefilled form and the challenge when applicable.
5. `POST /portal/api/submit` body `{"draft_id": "abc123", "captcha_answer": "12"}`. Returns 200 `{"confirmation_code": "DEMO1234"}`. Returns 403 `{"error": "captcha_required"}` when a challenge applies and the answer is missing or wrong (the right answer is the sum shown on the page). Returns 500 with `{"error": "server_error"}` when `portal_500` is active. Submitting an already submitted draft returns 200 with the same code (idempotent).
6. `GET /portal/api/submissions/{draft_id}` returns `{"submitted": true, "confirmation_code": "DEMO1234"}` or `{"submitted": false}`.
7. The challenge: the page shows "What is 7 plus 5?" and the correct answer is 12. The agent never solves it.

## 10. Contract tests (the coding agent writes these as part of each task card acceptance)

1. Each endpoint returns the exact keys listed above (use `TestClient` and assert key sets).
2. `GET /api/applications/{id}` returns every top level key even for a freshly matched application.
3. Event ordering is ascending and `after` is exclusive.
4. 409 behaviors for runs and handoff.
