# PHASE 3 IMPLEMENTATION: Intelligence & Verification (B09 - B12)

**Date**: Sunday October 11, 2026  
**Status**: Completed  
**Owner**: Memeshi (Backend & Agents)  
**Tasks Completed**: B09, B10, B11, B12  
**neatlogs Project ID**: `72601136-9c61-4e1b-8644-8f9d7a83aedf`  

---

## 1. Summary of Work Done

Phase 3 implements the core intelligence and verification pipeline of ScholarPilot: building institution intelligence dossiers, finding applicant-listing competitive edges without leaking sensitive facts, drafting grounded application essays and resumes, and running rigorous multi-step verification including deterministic checks, batched claim auditing, and adversarial challenges with `neatlogs` guardrails.

### Task B09: Researcher & Institution Dossiers
- Created `backend/app/agents/researcher.py`:
  - Wrapped `build_dossier` with `@agent_span("researcher")`.
  - Implements live web fetching using `httpx` with strict 10s timeout, followed by fallback to `backend/data/dossier_cache/{listing_id}.json`.
  - Regex-based HTML stripping within `tool_span("fetch_page")`.
  - Prompt injection defense: sanitizes page text with `<<<PAGE_TEXT ... >>>` boundary markers and explicit system prompt boundary rules.
  - LLM extraction via `call_llm("researcher_v1", ...)` extracting `about`, `selection_criteria`, `themes`, `preferred_skills`, and exact `snippets`.
  - Snippet verification: verifies each snippet is an exact case-insensitive substring of raw page text.
  - Degraded mode recovery: if live fetch fails and no cache exists, creates a `recovery_decision("research_down", ["cache", "degraded"])` and returns a marked degraded dossier with empty criteria.
  - Persists dossier via `db.save_dossier` and logs event via `db.add_event`.

### Task B10: Edge Finder & Angle Selector
- Created `backend/app/agents/edge_finder.py`:
  - Wrapped `find_edges` with `@agent_span("edge_finder")`.
  - Sourced fact isolation: extracts core facts, vault facts, and dossier criteria.
  - Sensitive fact safety: strips sensitive facts in `tool_span("strip_sensitive")` so family hardship or sensitive disclosures are never passed to the edge scoring prompt.
  - LLM scoring via `call_llm("edge_v1", ...)` evaluating angles and competitive alignment against institutional criteria.
  - Threshold filtering: retains edges with `score >= 0.6`, sorted by score descending, capped at the top 3.
  - Degraded dossier safety: when a dossier is marked degraded (`is_degraded=True`), enforces a hard rule permitting only `cv_bullet` source edges and sets an honest generic rationale.

### Task B11: Tailor (Grounded Draft & Revision)
- Created `backend/app/agents/tailor.py`:
  - Wrapped `tailor_full` and `tailor_revise` with `@agent_span("tailor")`.
  - Closed Grounding Set (`build_sources`): strictly merges core CV facts (`C1..`) and selected edge facts (`P1..`, `D1..`). Sensitive facts are strictly excluded.
  - Drafting via `call_llm("tailor_v1", ...)`: generates segmented essay draft with claim-to-source traceability (`source_fact_ids`).
  - Ungrounded claim dropping: post-validates that every cited source fact ID actually exists in the grounding set; invalid/invented source references are dropped.
  - Length constraint enforcement: strictly clips essay length to `listing.essay_word_limit` (with 10-word safety margin) at clean sentence boundaries.
  - Targeted Revision (`tailor_revise`): uses `call_llm("tailor_revise_v1", ...)` to surgically replace ungrounded or weak sentences based on verifier feedback while maintaining the closed grounding invariant.

### Task B12: Verifier (Deterministic Checks, Auditing, Adversarial Challenger & Mode A)
- Created `backend/app/agents/verifier.py`:
  - Wrapped verification routines with `@agent_span("verifier")`.
  - `deterministic_check`:
    - Wrapped in `tool_span("deterministic_claim_check")`.
    - Normalizes word numbers (e.g., "three" -> "3", "five" -> "5").
    - Validates numeric tokens and proper-name capitalized tokens against source text.
    - Sentence boundary exclusion: ignores capitalized tokens at sentence start (`[.!?]\s*`) to prevent standard sentence-initial words from false flagging.
  - `audit`:
    - Wrapped in `guardrail("verification_round")`.
    - Claims extraction via `call_llm("verifier_extract_v1", ...)`.
    - Batched claim judging via `call_llm("verifier_judge_v1", ...)` comparing claims to grounded facts.
    - Computes hallucination risk score based on unsupported and partial claims.
    - Logs neatlogs guardrail decision (`neatlogs.guardrail.passed`).
  - `challenge`:
    - Wrapped in `guardrail("adversarial_challenge")`.
    - LLM adversarial probe via `call_llm("challenger_v1", ...)` looking for exaggerated claims, duration misrepresentations, or title upgrades.
    - Sets pass/fail status and flags suspicious statements.
  - `verify_mode_a`:
    - Pure measurement mode: runs full audit, deterministic checks, and challenger.
    - Invariant: text is left completely untouched (read-only baseline verification).
    - Persists verification result to database and records run metrics.

---

## 2. Test Evidence & Validation

All 56 unit and integration tests across the backend test suite pass cleanly:
- `tests/test_researcher.py` (7 passed)
- `tests/test_edge_finder.py` (6 passed)
- `tests/test_tailor.py` (6 passed)
- `tests/test_verifier.py` (4 passed)
- Overall suite: 56 passed in 5.69s.
- Quick check: OK (56 tests passed).

---

## 3. How to Verify by Hand

Run tests directly from `backend/`:
```bash
cd backend
venv\Scripts\pytest tests/test_researcher.py tests/test_edge_finder.py tests/test_tailor.py tests/test_verifier.py -v
venv\Scripts\python scripts/quick_check.py
```
