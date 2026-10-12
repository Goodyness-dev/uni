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
