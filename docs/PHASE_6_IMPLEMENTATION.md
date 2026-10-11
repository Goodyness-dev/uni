# Phase 6 Implementation Document: Applier, Handoff & Failure Recovery Matrix (Tasks B21 & B22)

## 1. Overview & Objectives
Phase 6 delivers the autonomous execution and robust resilience layer for ScholarPilot:
- **Task B21**: Implementation of `applier.py` supporting package-only, direct email, standard portal form, and CAPTCHA-protected channels; blocker detection (HTML elements, iframes, password fields, login walls); Neatlogs `@agent_span("applier")` and `recovery_decision` spans; human-in-the-loop handoff with interactive Telegram inline buttons (`Done`, `Open`); and idempotent submission verification via `resume_after_handoff`.
- **Task B22**: Comprehensive failure injection regression matrix covering all 7 failure scenarios (`llm_429`, `bad_json`, `portal_500`, `captcha_wall`, `research_down`, `smtp_fail`, `injection_page`) with deterministic recovery decisions, Neatlogs `recovery_decision` CHAIN spans, structured database events, and verified evidence entries in `docs/17_EVIDENCE_CHECKLIST.md`.

---

## 2. Architecture & Components Implemented

### 2.1 The Applier Agent (`backend/app/agents/applier.py`)
- **Blocker Scanner (`check_blockers`)**:
  - Emits `TOOL` span `blocker_check`.
  - Scans target application URLs for:
    - `login_wall`: redirects to `/login` in response URL or redirect history.
    - `captcha_challenge`: presence of DOM element with id `captcha_challenge`.
    - `captcha_iframe`: embed iframes matching `recaptcha`, `hcaptcha`, or `turnstile`.
    - `password_input`: presence of `<input type="password">`.
- **Application Logic (`apply`)**:
  - `package_only`: Generates application packages and marks status as `prepared`.
  - `email`: Formats tailored summary and essay, calls `notify.send_email`, records submission code with channel `email`, and transitions to `submitted`. On `SmtpError`, triggers Neatlogs `recovery_decision("smtp_failure", ["retry", "prepare_package"])`, choosing `prepare_package` and setting status to `prepared`.
  - `portal_form` & `portal_captcha`: Creates idempotent drafts on `/portal/api/draft`, runs blocker scans, attempts submission on `/portal/api/submit` with exponential backoff on HTTP 500.
  - On persistent HTTP 500 (3 attempts): Triggers Neatlogs `recovery_decision("portal_500", ["retry", "email_fallback", "prepare_package"])`, choosing `email_fallback` if a committee email exists (and falling back to email dispatch) or `prepare_package`.
  - On blocker detection (e.g. CAPTCHA): Triggers Neatlogs `recovery_decision("captcha_wall", ["retry", "handoff"])`, chooses `handoff`, stores handoff draft details, transitions application to `awaiting_user`, and alerts applicant via Telegram with inline keyboard actions.
- **Handoff Resume (`resume_after_handoff`)**:
  - Synchronously updates state to `submitting`.
  - Queries portal verification endpoint `/portal/api/submissions/{draft_id}`.
  - If challenge was solved and submitted on portal: records confirmation code, transitions application to `submitted`, and emits `submission_confirmed` event.

### 2.2 Router Integration (`backend/app/routers/applications.py`)
- Added endpoint `POST /api/applications/{id}/handoff/done`:
  - Enforces status precondition `awaiting_user` (returns 409 Conflict if not awaiting handoff).
  - Transitions application to `submitting` synchronously.
  - Spawns background thread running `applier.resume_after_handoff(app_id)` to poll and confirm final submission status.

### 2.3 Failure Recovery Matrix (`backend/tests/test_recovery.py`)
Exercises all 7 failure injection modes:
1. **`llm_429`**: Primary rate limit -> 2 backoff retries -> `recovery_decision` -> fallback model (`gemini-2.5-flash-lite`).
2. **`bad_json`**: Truncated response -> `failure_injected` -> syntax repair at temperature 0.0 -> valid schema.
3. **`portal_500`**: 3 server error retries -> `recovery_decision` -> `email_fallback` to committee email -> `submitted`.
4. **`captcha_wall`**: Challenge detected -> `blocker_detected` -> `recovery_decision` handoff -> `awaiting_user` -> Telegram Done -> `submitted`.
5. **`research_down`**: Live fetch simulated error -> `failure_injected` -> `recovery_decision` -> `use_cache` -> cached dossier.
6. **`smtp_fail`**: SMTP failure -> `failure_injected` -> `recovery_decision` -> `prepare_package` -> `prepared`.
7. **`injection_page`**: Adversarial instructions dropped -> `injection_detected` -> sanitized dossier free of injection text.

---

## 3. Neatlogs Instrumentation & Depth
- **Span Decorators & Wrappers**:
  - `@agent_span("applier", role="applier", goal="submit verified scholarship applications")` wraps submission logic.
  - `@tool_span("blocker_check")` records portal inspection and detected blocker indicators.
  - `recovery_decision` CHAIN spans wrap all 7 mitigation paths, logging `recovery.trigger`, `recovery.options`, `recovery.chosen`, `recovery.reason`, and `recovery.outcome`.
- **Structured Events & Tags**:
  - Events logged: `failure_injected`, `blocker_detected`, `recovery_decision`, `retry`, `submission_confirmed`, `injection_detected`.
  - Span attributes recorded: `fallback_used`, `json_repaired`, `injection_dropped`.

---

## 4. Verification & Test Evidence
- **All 95 unit & integration tests passing**:
  - `test_applier.py` (5 tests)
  - `test_recovery.py` (7 tests)
  - `test_portal.py` (5 tests)
  - `test_notify.py` (6 tests)
  - `test_coordinator.py`, `test_verifier_mode_b.py`, and remaining pipeline suites.
- **Quick Check Validation**:
  - `python scripts/quick_check.py` passed with 0 banned imports, 0 untracked secrets, and 100% test pass rate.
