# 13_TASKS_BACKEND.md

Backend and agent task cards for Memeshi. Do them in order. One Antigravity conversation per card, using the master prompt in `12_ANTIGRAVITY_RULES.md` section 6.1.

Card format: Goal, Depends, Time box, Read (spec sections), Create or change (files), Requirements, Tests, Acceptance (run by hand), Commit.

How to verify by hand without command flags: start the server with `python run_server.py` and open `http://localhost:8000/docs` (FastAPI interactive docs) to call endpoints in the browser.

Tick each checkbox in the commit that finishes the card.

## B01. [x] Skeleton, config, errors, health

Goal: a running FastAPI app with the folder structure, settings, error classes and the health endpoint.
Depends: S01 to S10 done. Time box: 30 min.
Read: `04_ARCHITECTURE.md` sections 1 to 4, 9, 10, 12. `06_API_CONTRACT.md` section 2.
Create:
1. The folder structure from `04_ARCHITECTURE.md` section 4 (empty `__init__.py` files, placeholder modules can be empty).
2. `backend/app/config.py`: the `.env` loader (section 1 item 8) and a `settings` object with every environment variable from section 10, with the listed defaults, and helper properties `llm_primary_configured`, `llm_fallback_configured`, `telegram_configured`, `smtp_configured`, `neatlogs_configured`, `crustdata_configured`.
3. `backend/app/errors.py`: the error classes from section 12 and the `RunContext` dataclass.
4. `backend/app/main.py`: FastAPI app, CORS for `http://localhost:3000`, include the health router, a lifespan function that calls `init_db()` only when `app.db` exists as a module function (leave a TODO comment for later tasks), nothing else.
5. `backend/app/routers/health.py`: `GET /api/health` with the exact shape from the contract.
6. `backend/run_server.py`, `backend/pytest.ini`, `backend/requirements.txt`, `backend/scripts/quick_check.py` (spec in `07_AGENTS_SPEC.md` section 12.3), `.gitignore`, `.env.example` (all variable names, empty values, defaults where given).
Requirements: no other endpoints. `settings` must be importable without a `.env` file.
Tests (`tests/test_health.py`): health returns 200 and every key in the contract; `.env` loader sets variables from a temp file and does not override existing environment values.
Acceptance:
1. [ ] `python run_server.py` starts, `http://localhost:8000/api/health` shows the JSON.
2. [ ] `python scripts/quick_check.py` prints OK.
3. [ ] `.gitignore` contains `.env`, `backend/data/vault/`, `backend/data/app.db`, `backend/data/packages/`, `node_modules`, `.venv`, `.entire/settings.local.json`.
Commit: `feat(backend): fastapi skeleton, settings and health [B01]`.

## B02. [x] neatlogs tracing and the hello trace

Goal: `tracing.py` with init and all span helpers, plus a script that proves traces and a real Gemini call show up in neatlogs.
Depends: B01. Time box: 40 min.
Read: `09_NEATLOGS_SPEC.md` sections 1 to 4, `03_TOOLS_SETUP.md` sections 3 and 4.
Create:
1. `backend/app/tracing.py` with exactly the helpers in `09_NEATLOGS_SPEC.md` section 3: `init_tracing(tags)`, `shutdown_tracing()`, `workflow_span(name)`, `agent_span(name, role, goal)`, `tool_span(tool_name, description)`, `retriever_span(name)`, `guardrail(name)` (context manager), `llm_call_span(prompt_name, system, user, ctx)` (context manager), `recovery_decision(trigger, options)` (context manager), `set_attrs(span, **kwargs)`, `log_event(message, **kwargs)`.
2. FastAPI lifespan in `main.py` calls `init_tracing([])` at startup and `shutdown_tracing()` at shutdown (only when `settings.neatlogs_configured`).
3. `backend/scripts/trace_hello.py`: init tracing with tags `hello`, a WORKFLOW span containing an AGENT span containing a TOOL span, and ONE real chat call to the primary LLM with the OpenAI SDK against the primary base URL, client wrapped with `neatlogs.wrap`. Print the reply. Flush and shutdown at the end.
Requirements: helpers must no op safely (do nothing, never crash) when neatlogs is not configured, so tests run offline.
Tests: helpers work as no ops without a key (decorated function returns its value, context managers yield an object with a `set_attribute` method).
Acceptance:
1. [ ] Run the doctor check (`03_TOOLS_SETUP.md` section 3 item 4).
2. [ ] `python scripts/trace_hello.py` prints a model reply.
3. [ ] In the neatlogs dashboard: one trace with nested WORKFLOW, AGENT, TOOL spans and one LLM span showing the REAL model name, token counts and latency. If the model name or tokens are wrong, apply `NEATLOGS.md` fallback in `09_NEATLOGS_SPEC.md` section 9 (switch the primary client to the Google GenAI SDK).
4. [ ] Write the result in the blanks in `03_TOOLS_SETUP.md`.
Commit: `feat(tracing): neatlogs init and span helpers [B02]`.

## B03. [x] Models and database

Goal: all Pydantic models and the full SQLite layer.
Depends: B01. Time box: 50 min.
Read: `05_DATA_MODELS.md` sections 1 to 3, 6, `07_AGENTS_SPEC.md` section 1.1, `04_ARCHITECTURE.md` sections 6 and 9.
Create: `backend/app/models.py` (copy from `05_DATA_MODELS.md` section 1), `backend/app/db.py` with EVERY function listed in `07_AGENTS_SPEC.md` section 1.1 and the schema from `05_DATA_MODELS.md` section 2, plus seed rows for `failure_flags`.
Requirements:
1. `set_status` enforces the allowed transitions and raises `ValueError` otherwise. It must call `notify.on_status_change` through a lazy import and ignore the call when `notify` has no such function yet (keep a try and except ImportError around the import only).
2. `consume_flag` semantics exactly as in the spec.
3. IDs: run id `run_YYYYMMDD_NNN`, application id `app_N`.
4. The app database path is `backend/data/app.db`. Tests use a temp path through a settings override.
Tests (`tests/test_db.py`): every allowed transition passes and a few illegal ones raise; ids increment; `consume_flag` for counted and uncounted flags; JSON fields round trip; `replace_facts` and `add_vault_fact` id assignment (`P` ids continue after the highest existing).
Acceptance: [x] all tests pass. [x] `init_db()` called twice does not error.
Commit: `feat(db): models and sqlite layer [B03]`.

## B04. [x] The LLM wrapper (most important file)

Goal: `call_llm` with retries, fallback, JSON repair, failure hooks, cost and neatlogs attributes.
Depends: B02, B03. Time box: 70 min.
Read: `07_AGENTS_SPEC.md` section 1.2, `08_PROMPTS.md` sections 1 to 4, `04_ARCHITECTURE.md` sections 7 and 8, `09_NEATLOGS_SPEC.md` section 5.
Create: `backend/app/llm.py`, `backend/app/schemas.py` and `backend/app/prompts.py` (copy from `08_PROMPTS.md`).
Requirements: follow the algorithm in the spec step by step. Both clients lazy and wrapped with neatlogs. The model ids and base URLs come from settings only. Provide a module level function `set_clients_for_tests(primary, fallback)` so tests can inject fake clients. Record events (`retry`, `llm_fallback`, `json_repair`, `failure_injected`) only when `ctx.run_id` is not empty.
Tests (`tests/test_llm.py`) with fake clients: success; 429 then success; 429 twice then fallback success and `fallback_used` true; both fail raises `RateLimitError`; model not found goes straight to fallback; bad JSON repaired; bad JSON twice then regeneration; schema validation failure triggers repair; flag `llm_429` and `bad_json` injection consumed; token and cost math.
Acceptance:
1. [x] Tests pass.
2. [x] A small manual script (add to `scripts/trace_hello.py` as a second call) uses `call_llm` with a trivial schema and returns parsed data against the real model. The trace shows an LLM span named `llm.hello_v1` style with attributes.
Commit: `feat(llm): call_llm with retries, fallback and json repair [B04]`.

## B05. [x] Failure flags and the sensitive filter

Goal: flag endpoints and `sensitive.py`.
Depends: B03. Time box: 40 min.
Read: `06_API_CONTRACT.md` section 8, `07_AGENTS_SPEC.md` section 1.3, `10_FAILURES_AND_RECOVERY.md` section 3.
Create: `backend/app/failure_flags.py` (thin helpers over `db` flags: `flag_active(name)`, `consume(name, ctx)` which also records the `failure_injected` event), `backend/app/routers/flags.py`, `backend/app/sensitive.py`. Include routers in `main.py`.
Tests: sensitive tests listed in the spec; flags endpoints (set, counted, uncounted, reading back).
Acceptance: [x] set `llm_429` with count 2 through `/docs`, read it back, it shows enabled.
Commit: `feat(safety): failure flags and sensitive filter [B05]`.

## B06. [x] Data files: persona, listings, dossiers, portal about text

Goal: all demo data in place. This is mostly human work with Antigravity helping format.
Depends: B03. Time box: 90 min (spread over the morning).
Read: `11_DEMO_PORTAL_AND_SYNTHETIC_DATA.md` (all).
Create: `backend/data/synthetic/` files, `backend/data/listings.json` (5 entries), `backend/data/dossier_cache/*.json`, the about page text constants (used by the portal later), `backend/scripts/seed_persona.py`.
Requirements:
1. YOU copy the 2 real scholarship details by hand from official pages. Antigravity must not invent them. Leave a field empty rather than guess.
2. The persona must contain the 4 traps from `11_...` section 2.
3. A test loads `listings.json` through the `Listing` model and asserts exactly 5 listings, 3 mock, and that no field contains the word REPLACE (this test is expected to fail until you fill the 2 real entries, mark it as a final check).
Tests: `tests/test_data.py` (listings validate, persona files exist, traps present: the vault text contains `assistant coordinator`, the CV does not contain `president`).
Acceptance: [x] test passes. [x] you re read the persona and confirm it is fictional.
Commit: `feat(data): synthetic persona, listings and dossiers [B06]`.

## B07. [x] Intake and profile endpoints

Goal: facts from documents, profile endpoints, demo loader.
Depends: B04, B05, B06. Time box: 70 min.
Read: `07_AGENTS_SPEC.md` section 2, `06_API_CONTRACT.md` section 3, `08_PROMPTS.md` (intake).
Create: `backend/app/agents/intake.py`, `backend/app/routers/profile.py`.
Requirements: all steps in the spec including the number check and sensitive marking. `POST /api/profile/load_demo` reads `data/synthetic` and calls the same intake (404 when `DEMO_MODE` is false).
Tests: with fake `call_llm`: fact ids by source, altered numbers dropped, duplicates removed, sensitive keyword marking, PDF base64 path (generate a tiny PDF in the test with `reportlab`), endpoint shapes.
Acceptance: [x] via `/docs`: call `load_demo`, then `GET /api/profile/facts` shows `C`, `T`, `P` facts. [x] neatlogs shows `agent.intake` with LLM spans (real calls).
Commit: `feat(intake): fact extraction and profile endpoints [B07]`.

## B08. [x] Scout, Matcher and matches, gaps

Goal: ranked matches visible through the API.
Depends: B07. Time box: 60 min.
Read: `07_AGENTS_SPEC.md` sections 3 and 4, `06_API_CONTRACT.md` sections 5 and 7.
Create: `backend/app/agents/scout.py`, `backend/app/agents/matcher.py`, `backend/app/routers/matches.py`, `backend/app/routers/gaps.py`.
Requirements: hard rules exactly as specified. Gap creation (max 2 per application). `GET /api/matches` reads applications of the run.
Tests: each hard rule (with the GPA normalization example computed by hand), deadline boundary equals today passes, skipped listings carry failed rule names, fit score clamping.
Acceptance: [x] a temporary script or test creates a run row and runs Scout and Matcher, then `/api/matches` returns 5 entries with sensible scores. 
Commit: `feat(matcher): scout, hard rules and fit scoring [B08]`.

Checkpoint (Saturday 1:00 PM): Ayo can show real matches on the Matches screen. If not, stop and fix.

## B09. [x] Researcher (cache, live from our own portal, recovery)

Goal: dossiers from cache, with live fetch for mock listings, injection safety and the research recovery.
Depends: B04, B06. Time box: 70 min.
Read: `07_AGENTS_SPEC.md` section 5, `08_PROMPTS.md` (researcher), `10_FAILURES_AND_RECOVERY.md` sections 2 and 3.
Create: `backend/app/agents/researcher.py`.
Requirements: exactly the order in the spec. `fetch_page_text` strips HTML with regex (no HTML parser package). Injection scan and delimiters. Snippet verification. `research_down` flag.
Tests: cache load; no cache gives degraded dossier; invented snippet dropped; injection line dropped and event recorded; `research_down` on gives cache plus a recovery decision; HTML strip function.
Acceptance: [x] a script calls `build_dossier` for `mock_portal_masters` with the cache (works now) and for live after B20 exists (re test later).
Commit: `feat(researcher): sourced dossiers with cache and recovery [B09]`.

## B10. [x] Edge Finder

Goal: automatic selection of the strongest edges.
Depends: B09, B05. Time box: 50 min.
Read: `07_AGENTS_SPEC.md` section 6, `08_PROMPTS.md` (edge).
Create: `backend/app/agents/edge_finder.py`.
Tests: invalid ids dropped, threshold 0.6 and max 3, sensitive facts absent from the built prompt text, degraded dossier rule, gaps returned.
Acceptance: [x] a script prints the selected edges for the persona and `mock_portal_masters`; edges cite real fact ids and the reasons read honestly. Add `P7` style evidence check by eye.
Commit: `feat(edges): edge finder with validation and selection [B10]`.

## B11. [x] Tailor baseline

Goal: tailored output with source ids, no verification yet.
Depends: B10. Time box: 60 min.
Read: `07_AGENTS_SPEC.md` section 7, `08_PROMPTS.md` (tailor).
Create: `backend/app/agents/tailor.py` with `build_sources`, `tailor_full`, `tailor_revise` (revise can be a stub raising `NotImplementedError` until B15; implement it now if time allows).
Tests: segments with unknown source ids dropped, word limit enforcement path, `build_sources` includes edge facts and core facts only.
Acceptance: [x] a script prints the tailored CV summary, bullets and essay with source ids for the persona. Read it. Note anything that looks invented (this is run A material, do NOT fix the prompt to hide it).
Commit: `feat(tailor): baseline tailored output with sources [B11]`.

## B12. [x] Verifier audit and challenger (measurement only)

Goal: audit, deterministic check, challenge, mode A entry point.
Depends: B11. Time box: 90 min.
Read: `07_AGENTS_SPEC.md` sections 8.1 to 8.4, `08_PROMPTS.md` (verifier, challenger), `09_NEATLOGS_SPEC.md` section 4.
Create: `backend/app/agents/verifier.py` with `deterministic_check`, `audit`, `challenge`, `verify_mode_a` (leave `verify_mode_b` raising `NotImplementedError`).
Requirements: GUARDRAIL spans with `passed` set. Number word normalization. Batch size 10.
Tests: deterministic cases (number mismatch, missing source ids, number words, proper noun check), verdict combination table, mode A leaves text unchanged, challenge marks overturned.
Acceptance: [x] run `audit` on the tailored output from B11. The report lists claims with verdicts. In neatlogs the GUARDRAIL span shows Passed or Blocked.
Commit: `feat(verifier): audit and challenger measurement [B12]`.

## B13. [x] Coordinator v1, run endpoints, pipeline script, metrics

Goal: the whole chain runs from Intake data to a tailored and audited output per application, with events and metrics.
Depends: B12, B08. Time box: 90 min.
Read: `04_ARCHITECTURE.md` sections 5 to 8, `07_AGENTS_SPEC.md` section 12, `06_API_CONTRACT.md` sections 4 and 6, `05_DATA_MODELS.md` section 8.
Create: `backend/app/coordinator.py`, `backend/app/routers/runs.py`, `backend/app/routers/applications.py`, `backend/scripts/run_pipeline.py`. Update `main.py` to include routers and call `db.init_db()` and `db.mark_interrupted_runs()` at startup.
Requirements: `run_step` with retries and recovery decisions (the `recovery_decision` context manager from `tracing.py`). Steps after `verify` (package, apply) are placeholders that set the status `ready` for now. `compute_metrics`. Run thread with top level error handling. `GET /api/applications/{id}` returns ALL keys in the contract.
Tests: `run_step` retry then success, retry then fallback with a recovery decision event, failure of one application does not stop the next, metrics computation from stored reports, idempotent resume (step output exists means skipped), status transitions through the run.
Acceptance: [x] `python scripts/run_pipeline.py A 2 run_A,evidence` completes and prints metrics. [x] `/api/runs/latest`, `/api/applications/{id}` return full shapes. [x] neatlogs shows one WORKFLOW trace with the full agent tree.
Commit: `feat(coordinator): run loop, endpoints, metrics, pipeline script [B13]`.

## B14. [x] RUN A (before the enforcement code exists)

Goal: capture the baseline evidence BEFORE B15.
Depends: B13. Time box: 25 min.
Do not change code. Run `/run_ab` with mode A twice (tags `run_A,evidence`). Save the generated files under `docs/evidence/`. Screenshot the neatlogs traces (span tree, GUARDRAIL results, Analytics cost). Record the trace links.
Acceptance: [x] two files `run_A_1.json` and `run_A_2.json`. [ ] screenshots saved. [x] `17_EVIDENCE_CHECKLIST.md` section 2 filled for run A. [ ] Post draft written with the real finding (what the Tailor stretched).
Commit: `docs(evidence): run A baseline traces and metrics [B14]`.

## B15. [x] Verifier enforcement loop

Goal: `verify_mode_b` with revisions, removal, challenger integration, sensitive scan.
Depends: B14. Time box: 80 min.
Read: `07_AGENTS_SPEC.md` section 8.4 and section 7 (`tailor_revise`), `08_PROMPTS.md` (tailor_revise).
Create or change: `verifier.py` (`verify_mode_b`), `tailor.py` (`tailor_revise` implemented).
Tests: unsupported claim then fixed on revision round 1; unsupported twice then removed with a `RemovedClaim`; overturned claim path; sensitive scan removes text; `unsupported_final` is 0 in the happy path; revision replaces only the listed segments.
Acceptance: [x] `run_pipeline.py B 2 run_B,evidence` shows `unsupported_final` 0 on the persona. [x] neatlogs shows multiple guardrail rounds.
Commit: `feat(verifier): enforcement loop with revisions and removal [B15]`.

## B16. [x] RUN B and the comparison

Goal: capture the after evidence and the comparison table.
Depends: B15. Time box: 30 min.
Run mode B twice. Build the A versus B table (`17_EVIDENCE_CHECKLIST.md` section 2). Screenshot neatlogs. Do not cherry pick, report both runs or medians.
Commit: `docs(evidence): run B traces, metrics and comparison [B16]`.

## B17. [x] Improvement loop 1 with the neatlogs MCP

Goal: show that neatlogs was used to improve the agent.
Depends: B16 (and N04 style MCP setup in `03_TOOLS_SETUP.md`). Time box: 30 min.
Use `/read_trace` for the run A tag. Record in `docs/evidence/improvement_log.md`: trace link, finding, the change made in B15, commit hash, Entire checkpoint, before and after numbers. If the MCP is not connected, do the same by hand and write that honestly.
Commit: `docs(evidence): improvement log entry 1 [B17]`.

## B18. [x] Notifications and the Telegram poller

Goal: Telegram messages at each step and the Done button.
Depends: B13. Time box: 70 min.
Read: `07_AGENTS_SPEC.md` section 1.4, `05_DATA_MODELS.md` section 7.
Create: `backend/app/notify.py` (templates, `send_telegram`, `send_email`, `on_status_change`, `retry_unsent`, `start_poller`). Hook `start_poller` into the lifespan when Telegram is configured. Call `send_event` for matches found and edges used from the Coordinator.
Tests: template wording for each template, `send_telegram` writes the notification row and marks sent on a fake httpx response, failure leaves `sent` false and does not raise, `retry_unsent`.
Acceptance: [x] run the pipeline and receive messages on your phone for matches, researched, verified. [x] The handoff message has Done and Open buttons (check after B21).
Commit: `feat(notify): telegram and email notifications [B18]`.

## B19. [x] Packager

Goal: CV PDF, essay file, checklist.
Depends: B15. Time box: 45 min.
Read: `07_AGENTS_SPEC.md` section 10.
Create: `backend/app/agents/packager.py` and the file endpoint in `routers/applications.py`.
Tests: files created for a sample tailored output, only supported segments included, removed segments excluded, checklist content.
Acceptance: [x] open the generated `cv.pdf` and read it. [x] `GET /api/applications/{id}/files/cv` downloads it.
Commit: `feat(packager): cv pdf, essay and checklist [B19]`.

## B20. [x] Demo portal backend

Goal: the portal routes and templates (Ayo supplies HTML styling in F07; you provide minimal working templates first).
Depends: B03, B05. Time box: 60 min.
Read: `06_API_CONTRACT.md` section 9, `11_DEMO_PORTAL_AND_SYNTHETIC_DATA.md` section 5.
Create: `backend/app/portal/routes.py` and minimal Jinja2 templates in `backend/app/portal/templates/` (`about.html`, `apply.html`, `draft.html`, `confirmation.html`, `error.html`). Serve templates with Jinja2 directly (no extra package). Include the router at the root (not under `/api`).
Requirements: exact behaviors in the contract: idempotent draft by key, CAPTCHA element with id `captcha_challenge` when the flag is on or the listing channel is `portal_captcha`, 403 when the answer is missing or not 12, 500 when `portal_500` (counted flag), idempotent submit, injection paragraph on the about page when `injection_page` is on.
Tests (`tests/test_portal.py`): draft idempotency, captcha required and then accepted with 12, 500 flag consumed, submit idempotent, submissions endpoint, about page contains the school text.
Acceptance: [x] open `http://localhost:8000/portal/about/mock_portal_masters` and `/portal/apply/mock_portal_masters` in a browser. [x] submit the form by hand and see the confirmation code.
Commit: `feat(portal): demo portal routes and templates [B20]`.

## B21. [ ] Applier, handoff and resume

Goal: the main agentic layer.
Depends: B18, B19, B20. Time box: 100 min.
Read: `07_AGENTS_SPEC.md` section 11, `04_ARCHITECTURE.md` section 8, `10_FAILURES_AND_RECOVERY.md` section 2.
Create: `backend/app/agents/applier.py`, the handoff endpoint in `routers/applications.py`, update the Coordinator `apply` step to call it.
Requirements: channel handling exactly as specified, blocker detection from HTML, idempotency, recovery decisions, `resume_after_handoff`, status mapping, Telegram handoff message with buttons.
Tests: blocker detection on three HTML fixtures (captcha element, recaptcha iframe, password input, clean page), portal 500 retries then fallback decision, 403 treated as blocker, confirmation polling, idempotent submit, `resume_after_handoff` true and false cases, email path with a fake SMTP.
Acceptance:
1. [ ] Mock portal listing without CAPTCHA: status `submitted` with a confirmation code.
2. [ ] `portal_captcha` listing: status `awaiting_user`, Telegram message arrives, solve the challenge on the draft page, press the Done button in Telegram, status becomes `submitted`.
3. [ ] Email listing: message arrives in the demo inbox.
4. [ ] Real listings end as `prepared`.
Commit: `feat(applier): channels, blockers, handoff and resume [B21]`.

## B22. [ ] Failure injection runs and recovery decisions

Goal: evidence for every recovery.
Depends: B21. Time box: 60 min.
Use `/inject_failure` for `llm_429`, `bad_json`, `portal_500`, `captcha_wall`, `research_down`, `smtp_fail`, `injection_page`. For each: confirm the events (`failure_injected`, `recovery_decision`), confirm the neatlogs trace shows the failed call and the recovery with its reason, take a screenshot, and write the entry in `17_EVIDENCE_CHECKLIST.md` section 3. Fix any recovery that does not behave as the matrix in `10_FAILURES_AND_RECOVERY.md` says.
Commit: `test(recovery): recorded failure and recovery runs [B22]`.

## B23. [ ] Challenger tuning with the persona traps

Goal: make sure the traps are caught.
Depends: B15. Time box: 45 min.
Add regression tests in `tests/test_traps.py` using fake LLM outputs that reproduce the traps: assistant coordinator upgraded to president (must be unsupported or overturned), "years of experience" claim (unsupported), sensitive fact (removed by the scan). Then run the real pipeline and read the report. Tune only the Verifier and Challenger prompts (new versions `verifier_judge_v2` and so on) if a trap slips through, and note the change in the improvement log.
Commit: `test(verifier): persona trap regression tests [B23]`.

## B24. [ ] neatlogs depth

Goal: everything in `09_NEATLOGS_SPEC.md` sections 6 to 10.
Depends: B16, B22. Time box: 120 min across the evening.
Do, in order: create the 15 detections (`10_FAILURES_AND_RECOVERY.md` section 6), add `trace_url` to runs and applications (contract change, tell Ayo), the evaluation script, improvement loop 2 and run C, voting and comments, Investigate threads, Analytics screenshots, Session Replay of the handoff.
Commit: several, prefix `feat(neatlogs)` or `docs(evidence)`, ids `[B24]`.

## B25. [ ] Final clean run and backup recording (Monday morning)

Run the full demo path on the persona in mode B. Record a backup screen recording of the whole runtime section. Fix only bugs. Seed the database to a known state for the demo.
Commit: `chore(release): final clean run and demo seed [B25]`.

## B26. [ ] Info and Draft Pack mode (optional, cut early if short)

Goal: restricted AI policy listings.
Depends: B21. Time box: 60 min.
Read: `07_AGENTS_SPEC.md` section 9, `08_PROMPTS.md` (outline).
Implement `tailor_notes_only`, the Coordinator branch, the briefing messages, and the packager handling of the outline.
Tests: restricted listing never produces essay prose, bullets equal original fact text exactly, outline ids valid.
Commit: `feat(pack): info and draft pack mode [B26]`.

## B27. [ ] Gap answers endpoint polish (optional)

Gap endpoints exist from B08. Add the Telegram gap message and make sure answering creates a vault fact. Commit: `feat(gaps): gap questions and answers [B27]`.

## B28. [ ] Stretch: live Crustdata research

Only after everything else. Implement the Crustdata path in `fetch_live` using the Crustdata docs, 8 credits per scholarship budget, record `credits_used`. Never use the human mode option. Time box 45 minutes. Commit: `feat(research): crustdata live research [B28]`.

## Critical path summary

B01, B02, B03, B04, B07, B08 (Saturday), then B09, B10, B11, B12, B13, B14 (RUN A), B15, B16 (RUN B), B17, B18 to B22, B24, B25. If time runs out, cut B28, B27, B26, B23 in that order. Never cut B14 to B17, B21, B22.
