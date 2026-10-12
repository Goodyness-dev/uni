# Production repair plan — 2026/10/12

Scope: the user's request to repair the 22 audited README claims. Existing user edits are preserved. No real scholarship submissions, paid model calls, deployments, external notifications, or new dependencies are used for validation. This request authorizes implementation now; a separate approval round is not required.

## 1. Critical safety gates (implement first)

1. Managed storage: resolve paths beneath `storage/documents/<user UUID>`; reject traversal, symlinks, absolute external paths and another user's files. Never delete arbitrary client-supplied paths. Functions: `managed_document_path(user_id: UUID, storage_key: str) -> Path`, `remove_managed_file(path: Path, root: Path) -> bool`. Files: documents/account endpoints, storage helper. Tests: cross-user paths, traversal, symlink escape, nonexistent files, valid deletion. Do not mark metadata as verified without reading and checking evidence.
2. Eligibility: stop the coordinator when no profile or eligibility failure is returned. No default fit score. Use an existing terminal state and an explicit audit event. Tests: ineligible/missing profile never drafts or queues submission.
3. Submission: reject illegal states, missing/empty drafts, inactive owners, non-demo origins, missing browser, unconfirmed result and implicit mock fallback. Require Redis lease in production, recheck kill switch just before the click and scan for post-submit blockers. Ambiguous success requires human review and must never be automatically resubmitted.
4. Authentication: prevent unauthenticated key creation for an existing email from exposing another user's account. Production bootstrap must fail closed pending a verified identity flow. No new authentication UI in this task.

## 2. Four open claims

### Claim 5 — daily scheduled discovery
Add a worker scheduler tick with timezone-aware local daily buckets and Redis NX deduplication. Use stored catalog only and describe it as catalog matching, not live discovery. Enqueue `daily_scheduler` jobs using existing Job payload. Respect shutdown and do not send notifications during tests. Validate timezone boundaries, same-day repeat ticks, restart deduplication, failed scheduling and worker registration.

### Claim 9 — duplicate submission prevention
Hold an application-specific Redis token lease across the complete submitter call. Release with compare-and-delete Lua. Fail closed in production without Redis. Reject direct calls from invalid states. Do not retry outcomes whose acceptance is unknown. Validate competing callers, expired/mismatched release tokens, already-confirmed applications and retry after failure before click. Describe remaining portal-level exactly-once limitations honestly.

### Claim 18 — append-only audit
Keep ordinary workflow events append-only; verify all state updates use `transition_application`. Account erasure and permanent event retention conflict: preserve identifiers/tombstones only if no personal payload remains, and document the retention policy. Do not claim immutable retention unless PostgreSQL permissions/triggers are actually tested. No silent deletion of audit rows or untested compliance claim. Validate state/event atomicity, retention and erasure under real foreign keys.

### Claim 21 — verified profile/document evidence
Metadata registration is not verification. Return `verified=False`, do not inflate completeness, and validate file ownership. Profile data remains user-provided until a real evidence verification workflow exists. Correct README terminology rather than implementing fake verification. Tests: arbitrary type/storage key cannot produce a verification result.

## 3. Fourteen partially implemented claims

1. Autopilot: enforce eligibility, restart-safe coordinator stages, persisted draft requirement and safe demo-only submission. Test every stage and failures between commits.
2. Redis broker: database is source of truth; atomic conditional job claim; respect scheduled timestamps on both dequeue paths; reconcile missed Redis messages. Test multiple workers and queued duplicates.
4. Retry/dead-letter: rollback failed transaction, bounded retry/backoff, automatic requeue and manual dead-letter recovery. Reclaim crashed running jobs conservatively; never retry ambiguous external submissions. Test attempts, terminal threshold, scheduled delay and process restart.
6. Deadline alerts: use Telegram chat ID, bucket deduplication, active-user filtering and delivery success accounting. Test 7/3/1 day boundaries and failed sends.
8. Kill switch: Redis shared runtime key plus configured stop flag; recheck before click. State change is not cancellation of an already accepted request. Test API/worker shared state and mid-work stop.
11. Handoff: save only managed session state, stop on blockers and emit notification/audit. Resume must recheck the blocker in the same accessible session; headless saved cookies alone are not a complete human handoff. Never bypass login/CAPTCHA. Test stop/resume and absent session.
13. Spending: reserve cost atomically per user/global daily Redis keys, reconcile actual costs including paid invalid outputs, avoid refunds for billed calls, and retain across workers. Enforce maximum output tokens. Test cap races, rollover, failure and fallback. Do not claim hard caps for estimates that can exceed their reservation.
14. Tracing: initialize/flush once in API and worker, async-aware decorators, workflow/agent/tool/guardrail spans and recovery events. Never log draft bodies. Verify with fake neatlogs; actual dashboard/deep-link evidence remains a separate live check.
15. Research: remove generated institutional facts; retain only literal public page evidence. Reject non-public destinations, redirects to private IPs, injection instructions, login walls and empty fetches. Test fake HTTP responses and provenance.
16. Edges: remove invented degrees, nationality, GPA scale, leadership and fixed fit metrics. Select actual profile facts; do not treat a research sentence as proof of personal achievement. Validate empty/missing facts and different GPA scales.
17. Verifier/drafting: replace topical-word acceptance with conservative exact evidence support; no automatic unsupported prose. Sentence-specific source mapping. Preserve original user statements; distinguish an extractive baseline from LLM drafting, challenger and revision workflows that require further implementation. Test invented titles/numbers/duration/causal claims and empty drafts.
19. Migrations: add a forward migration for deployments at revision 001; do not rely on editing applied migration. Check UUID columns, Job payload, indexes and event foreign keys against ORM, fresh install and upgrade. Run PostgreSQL verification only against an isolated database.
20. Privacy logging: redact sensitive fields and tracebacks, avoid full prose in messages/spans and exception text. Validate names/essay/IDs/keys/log extras and raw exception output. No claim of universal automatic PII detection.
22. Export/erasure: managed files only, delete session-state artifacts, remove jobs containing user/application IDs, prevent queued execution after erasure, resolve audit FK restrictions and return failures honestly. Export references explicitly; do not claim a complete archive when file bytes are absent. Test ownership and PostgreSQL constraints.

## 4. Revalidate the four previously closed gaps

3. Compose worker stays alive and shuts down cleanly. 7. Approve/resume enqueue exactly one runnable job. 10. Missing confirmation cannot produce submitted status; mocks require explicit test mode. 12. Rate-limit integration covers all v1 routes; production shared limits and trusted proxy handling need separate checks.

## 5. Additional validation and evidence

* Root pytest suite, new safety regressions, backend quick check, frontend type check/lint if API behavior changes affect the demo client.
* Tests use temporary SQLite with foreign keys enabled, fake Redis and mocked HTTP/LLM/browser/notifications; no live keys or network.
* Isolated PostgreSQL migration/constraint tests, real Redis worker races/restart tests, Docker Compose health/worker smoke test and local demo browser submission/handoff test are distinct checks. Report unavailable runtimes rather than fabricate results.
* Readiness must include required broker/schema state. No production key issuance by knowing a victim's email; no default production secrets or world-exposed database/broker ports.
* Preserve user changes; inspect diffs and staged files before committing. Never commit environment files, database files, generated packages or screenshots containing personal data.
* README and evidence: identify implemented, limited and unverified features. Remove unsupported 15-detection, measured-cost, compliance, exactly-once and zero-hallucination assertions. Fresh real traces, metrics and sponsor dashboard evidence must be collected by an authorized live run later.

## 6. Acceptance and reporting

Safety fixes are complete only when regressions reproduce the original issue and pass with the repair. Each remaining operational/live integration check is recorded as pending with a concrete command or procedure. Report changed files, commands/results, remaining limitations and manual verification. Never equate passing unit tests with production readiness.

## 7. Implementation and verification record

### Completed repair batch

* Managed document paths and file erasure; no type-only verification or completeness inflation.
* Eligibility rejection, GPA scale comparison and removal of fabricated degree/nationality defaults.
* Extractive evidence-only drafts and conservative exact-source verification. Empty supported output stops work. This does not claim a completed LLM Challenger.
* Atomic database claims, persisted payloads, scheduled retry delays, stale internal job recovery and dead-letter handling for uncertain submissions.
* Redis submission leases, shared global/account stop keys, strict local demo origin restriction, before-click guards and post-submit blocker scans.
* Demo draft idempotency and authoritative confirmation API readback. Unknown acceptance blocks retries; saved session state is scoped to an application artifact directory.
* Worker daily scheduling with timezone/local-date Redis deduplication; correctly addressed, deduplicated deadline alerts. UTC/Lagos fixed-offset fallback supports Windows without additional dependencies; other zones need system timezone data.
* Production Redis budget reservations and reconciliation, no implicit fake provider success, asynchronous retry sleep and no model bodies in failure logs.
* API/worker tracing initialization through `backend/app/tracing.py`, async decorators and guardrail input lengths. Neatlogs is an architecture-approved dependency added to root requirements.
* Production email-only key issuance disabled; existing identities cannot mint new keys through unauthenticated email recovery.
* Forward migration 002 adds payload, casts PostgreSQL identifiers and repairs audit FK. Original applied migration restored rather than rewritten.
* Docker worker command, private database/broker port bindings, required database password, shared browser binary directory and fail-on-install behavior.
* README rewritten to distinguish implemented code, conservative baseline, pending integration and unsupported evidence.

### First-batch measured checks

* Final root pytest: **57 passed in 17.21 seconds**, including account-stop/blocker refinements and confirmation API regression.
* Backend quick check: 99 passed; banned-import and secrets checks passed. A configuration-dependent JSON recovery test now uses an explicit fictional client.
* Isolated SQLite migration: revision `002_repair_queue_schema`, Job payload present, audit FK uses RESTRICT.
* Frontend TypeScript check and ESLint: successful; no frontend files changed.
* `git diff --check`: successful.

### Approved second implementation batch

User approved the identity-token endpoint and production frontend adapter extension on 2026/10/12. Contract: `PRODUCTION_V1_CONTRACT.md`. Implemented:

* Fresh RS256 identity tokens with pinned issuer/audience/JWKS, verified matching email, subject binding, Redis single-use exchange and read/write scope enforcement. Existing inactive identities are rejected. New identities default to review mode.
* Source-aligned applicant document review with owned bounded PDF/text uploads, reserved provenance, literal excerpts, content digests and invalidation after source changes. Sensitive facts are excluded. This is not authenticity certification or OCR.
* Independent generated sentence judgment and adversarial Challenger calls, deterministic source checks, at most two revisions, removal of unsupported content, persisted verification/usage records and source-built CV PDF/writing/checklist packages. Live model calls stay opt-in.
* Public HTTPS research with private/mixed DNS rejection, pinned resolved addresses/TLS hostname, no redirects/proxies, bounded text retrieval and persisted research evidence.
* Renewable Redis submission leases and ownership recheck immediately before clicking, shared credential/IP rate windows, scope checks and clean cached Redis shutdown.
* Database audit UPDATE/DELETE guards, with owner-scoped privacy erasure. Migration 003 installs guards after the existing forward schema repair.
* Optional document-byte export, package cleanup on erasure and production worker-stop requirement. Files outside owned storage are never removed.
* Actual database-backed batch runs and authenticated frontend integration on the existing four screens: identity token exchange, source review, packages, approval and confirmation-only handoff. Missing metrics, trace IDs and eligibility breakdowns remain absent. The demo API remains intact.
* Resume never creates another submission after a human handoff: it requires authoritative demo confirmation. Unknown/restricted AI policy prevents automatic submission even through a direct worker call.
* API validation errors exclude submitted values, model failures exclude generated content, and structured exception logging records only exception types.

### Claim acceptance matrix after implementation

| Claim | Code status | Evidence still needed |
| --- | --- | --- |
| 1 Autopilot | Implemented for eligible, allowed-policy local demo listings; real listings/manual policy produce packages | Actual Chromium + real worker |
| 2 Redis broker | Database claims, wakeups, persistence and scheduled polling implemented | Real broker crash/race/restart |
| 3 Worker process | Long-running worker and shutdown implemented | Compose lifecycle |
| 4 Retry/dead-letter | Bounded internal retries and conservative uncertain-submission recovery | Process termination test |
| 5 Daily schedule (open) | Local-date/timezone deduplication implemented | Real Redis and timezone data |
| 6 Deadline alerts | Owner chat ID, buckets, dedup and delivery accounting implemented | Authorized Telegram delivery |
| 7 Approval/resume | Draft/policy checks; demo approval queues; Resume reconciles confirmed human submission | Live demo handoff |
| 8 Kill switch | Shared/account stop plus before-click guard implemented | Mid-browser stop/race |
| 9 Duplicate prevention (open) | Renewable token lease, portal idempotency and authoritative readback | Real expiry/crash test; no universal exactly-once claim |
| 10 Confirmation | Only authoritative own-portal confirmation accepted | Actual portal/browser run |
| 11 Handoff | Own demo draft accessible to human; Resume does not resubmit | CAPTCHA interaction by human; external login/MFA excluded |
| 12 Rate limits | Production shared Redis credential/IP windows; development local limiter | Real Lua and proxy configuration |
| 13 Spending | Shared reservations, billed retries and provider usage accounting; absent usage not invented | Real provider usage/pricing and Redis concurrency; estimates remain conservative |
| 14 Tracing | Shared init, workflow/agent/tool/guardrail helpers; guessed dashboard URLs removed | Actual sponsor traces, detection rules, analytics and trace IDs |
| 15 Research | Bounded pinned public retrieval and literal source evidence implemented | Actual TLS/egress/source quality; cache remains process-local |
| 16 Edges | Original reviewed/profile evidence selected without invented experience | Semantic usefulness; frontend edge panel still has no independent edge IDs |
| 17 Verifier/drafting | Generation, independent judge/Challenger, bounded revision and packages implemented | Live quality evaluation; no zero-hallucination promise |
| 18 Audit (open) | Database guard with explicit governed erasure implemented | Real PostgreSQL privileges/triggers; no privileged-tamper guarantee |
| 19 Migrations | Forward 002 and audit 003 implemented; SQLite upgrade checked | Populated PostgreSQL 001 upgrade and parity |
| 20 Privacy logging | Sensitive keyed values, input exclusions and exception-type logging implemented | Broader log audit; free-text PII recognition is not universal |
| 21 Verified profile (open) | Literal source review + digest provenance implemented | Not authenticity certification; scanned PDFs/OCR unsupported |
| 22 Export/erasure | Local document bytes, packages, session artifacts, events and owned jobs handled | Remote objects, distributed file/DB recovery and real PostgreSQL |

### Remaining acceptance work, most important first

1. Run isolated PostgreSQL migration 001 -> 003 with populated fictional records, schema parity and governed erasure. Verify application database permissions cannot disable audit guards.
2. Run real Redis multi-worker claims, lease renewal/loss/crash, broker outage, daily dedup, shared rate Lua and budget-reservation races. Doubles cannot establish these deployment properties.
3. Build/start Compose with operator-provided secrets, inspect `/ready` including schema/broker checks, worker shutdown and owned artifact volumes. Docker/PostgreSQL/Redis server are unavailable on this host.
4. Start the original localhost:8000 demo portal, the root API on a separate port, and real Chromium. Run fictional upload/review/package/approval/handoff and confirm one portal submission. No browser or deployed identity-provider flow was verified here.
5. Validate the actual pinned identity provider and complete its ordinary browser sign-in/redirect integration. The implemented top-bar control exchanges a token; it does not provide a hosted provider sign-in screen.
6. Authorize and collect live model quality/usage, real sponsor traces/detection/analytics evidence and delivered notifications. No external notifications or paid model calls were made for these tests.
7. Design reviewed remote-object erasure, backup retention and compensating filesystem/database recovery. Local file deletion is not an atomic distributed transaction.
8. Add stable event sequence IDs under a separately reviewed model change; the batch API currently uses snapshot ordinals. Integrate independently identified source edges in the frontend if that panel is required.

No regulatory compliance, deployed sponsor evidence, live unit economics or production readiness follows from this batch.

### Latest measured checks (approved extension)

* Root pytest: **74 passed in 21.68 seconds**, including identity replay/claim rejection, source invalidation, audit mutation denial, lease ownership loss, owned package downloads/erasure, shared credential/IP limits, confirmation-only handoff, paid invalid-output usage accounting and missing-schema readiness.
* Original backend quick check: **99 passed in 35.17 seconds**; banned-import and untracked-secret checks passed.
* Frontend TypeScript and ESLint: passed after v1 integration.
* Isolated fresh SQLite migration 001 -> 002 -> **003_audit_guards**: passed; both audit triggers present and event FK uses RESTRICT.
* Whitespace/diff checks: passed. No live model, provider login, sponsor/dashboard, real Redis/PostgreSQL, container or Chromium evidence was collected.

## Local end-to-end integration — 2026/10/12

User authorized connecting the frontend and running a full fictional application through real PostgreSQL/Redis, API, worker and demo portal. Files: `frontend/lib/api.ts`, `frontend/lib/v1.ts`, Next rewrites and existing four screens; `scripts/import_catalog.py`, `scripts/local_demo.py`, `scripts/verify_local_demo.py`, blocker detection and its regression. Existing tracing helpers remain in place; no fabricated sponsor spans or live-model metrics are added.

Completed with real localhost services:

* PostgreSQL **16.11**, isolated database `scholarpilot_demo` on loopback port 55432; migration **003_audit_guards** applied. Ordinary audit UPDATE/DELETE attempts were rejected inside rolled-back transactions.
* Redis **7.4.9**, the redis-windows Cygwin distribution, on loopback port 16379 with authentication. Archive SHA256 matched publisher metadata. Real Lua lease competition and token release passed.
* Frontend on localhost:3000 uses same-origin Next rewrites to the root API on localhost:8001. The existing demo portal remains on localhost:8000. The real worker executes persisted PostgreSQL jobs, Redis wakeups and installed Chromium.
* Connected the existing fictional Tobi Adeyemi identity through the development endpoint in the UI. Uploaded CV, transcript and non-sensitive vault statements from `backend/data/synthetic/`; reviewed **33 facts across 3 documents** through the UI. Production token requirements were not relaxed.
* Fixed country-name mapping, restoration after review/reload, missing development credential connection, encoded dynamic route folders, required Next Suspense boundaries, ISO date parsing, misleading all-complete/verification labels, source citations/edges and authenticated downloads.
* Fixed catalog application URLs: local demo submissions use the actual `/portal/apply/...` path rather than the institutional about page. Kept the original full-name field intact during draft creation.
* First run exposed a false blocker from a static JavaScript error string. The actual portal had no challenge. Completed its challenge-free form and frontend confirmation-only handoff; receipt **DEMO4907**. Resume did not queue a second submission.
* Removed script/style text from blocker matching while preserving real challenge/password/widget markup. A regression proves actual challenge and login markup still block. Second application was submitted by the worker itself; authoritative receipt **DEMO1668**, application `b32ebee0-1fa9-4095-a914-f3a97b506f15`, run `ac7eae64-756e-419f-a5fd-8f31553aa379`. The frontend visibly showed Submitted and all stages complete.
* Authenticated CV PDF download completed in the browser. Six package files were generated across the two applications. No CAPTCHA was solved or bypassed.

Evidence: `docs/evidence/fictional_e2e_20261012.json` records actual versions, IDs, receipts, jobs, reviewed counts, file sizes/digests and live guard/lease results. Screenshot: ignored `storage/screenshots/fictional_e2e_success.png`.

Validation: **75 root tests passed in 32.30 seconds**, **99 original backend checks passed in 46.53 seconds**, frontend type check/ESLint passed after route type regeneration. The local run used extractive source text: LLM drafting, public research, sponsor export and external notifications were disabled. Paid model quality, real identity-provider redirects, remote object deletion, populated historical migration upgrade and Linux/Docker deployment remain unverified.

Start/reuse this workstation runtime: `backend/.venv/Scripts/python.exe scripts/local_demo.py start`. Stop it: the same command with `stop`. Recollect real evidence: `backend/.venv/Scripts/python.exe scripts/verify_local_demo.py`. Runtime binaries, credentials, portal database and logs stay beneath ignored storage. The services are left running for the user. The development PostgreSQL role is privileged; it is not a production permission configuration.
