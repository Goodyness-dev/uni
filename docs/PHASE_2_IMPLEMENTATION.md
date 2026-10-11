# PHASE 2 IMPLEMENTATION: Synthetic Data, Intake Agent, Scout, Matcher & Matches/Gaps APIs

**Date**: Sunday October 11, 2026  
**Status**: Completed  
**Owner**: Memeshi (Backend & Agents)  
**Tasks Completed**: B06, B07, B08  
**neatlogs Project ID**: `72601136-9c61-4e1b-8644-8f9d7a83aedf`  

---

## 1. Summary of Work Done

1. **Task B06 — Synthetic Persona, Listings, Dossier Caches & Portal Content**:
   - Created persona files in `backend/data/synthetic/`:
     - `cv.txt`: Tobi Adeyemi's CV (5-month BrightGrid internship, FSU Tech Club member, SunTrack project).
     - `transcript.txt`: CGPA 4.30 out of 5.00.
     - `preferences.json`: Field, country, funding, and GPA preferences.
     - `vault.json`: 10 vault sections including "assistant coordinator" and family income hardship.
   - Preserved all 4 verification regression traps:
     1. Title upgrade trap: Vault has "assistant coordinator", CV has "Member", never "president".
     2. Duration trap: 5-month internship, never "years of experience".
     3. Gap trap: Missing public policy experience for Northlight Graduate Award triggers gap question.
     4. Sensitive trap: Family income hardship fact marked sensitive.
   - Populated `backend/data/listings.json` with exactly 5 listings (3 mock: `mock_portal_masters`, `mock_captcha_award`, `mock_email_award`; 2 real scholarships for Nigerian applicants: Chevening Scholarships and Commonwealth Master's Scholarships) with zero `REPLACE` placeholders.
   - Populated 3 dossier caches in `backend/data/dossier_cache/` with exact snippet excerpts.
   - Created `backend/app/portal/content.py` with `ABOUT` text constants for the mock institutions.
   - Built `backend/scripts/seed_persona.py` to seed persona into SQLite.

2. **Task B07 — Intake Agent & Profile Router**:
   - Created `backend/app/agents/intake.py`:
     - Wrapped with `@agent_span("intake")`.
     - Supports plain text and base64 PDF via `pypdf`.
     - Splits documents into paragraph chunks <= 6000 characters.
     - Calls `call_llm("intake_v1", ...)` for each chunk.
     - Maps vault sections to normalized categories.
     - Deterministic number validation with regex `\d+(?:\.\d+)?` (drops hallucinations where numbers were not in source text).
     - Strips duplicates and flags sensitive categories/stems.
     - Assigns IDs: `C1..` (CV), `T1..` (Transcript), `P1..` (Vault).
     - Persists facts via `db.replace_facts` and preferences via `db.set_preferences`.
   - Created `backend/app/routers/profile.py`:
     - `POST /api/profile/intake`: runs intake, returns 201 with facts, counts, warnings.
     - `POST /api/profile/load_demo`: loads synthetic files and runs intake (404 when `demo_mode` is false).
     - `GET /api/profile/facts`: returns facts and preferences.
     - `PATCH /api/profile/facts/{fact_id}`: edits fact text.
     - `POST /api/profile/facts`: adds new vault fact with `P` ID.

3. **Task B08 — Scout, Matcher, Matches & Gaps Endpoints**:
   - Created `backend/app/agents/scout.py`:
     - `load_listings()`: wrapped in `@retriever_span("scout")`, loads and validates `listings.json`.
     - `filter_open(listings, today)`: partitions listings into open and expired lists based on deadline.
   - Created `backend/app/agents/matcher.py`:
     - `hard_rules(listing, prefs, today)`: wrapped in `@tool_span("hard_rules")`, evaluates 6 strict rules:
       1. Country
       2. Level
       3. GPA normalization: `(prefs.gpa / prefs.gpa_scale) >= (listing.min_gpa / listing.gpa_scale)`
       4. Field substring containment
       5. Deadline boundary (today passes)
       6. Nationality
     - `score_fit(listing, facts, ctx)`: strips sensitive facts, calls `call_llm("matcher_v1")`, clamps fit score to 0..100, extracts up to 2 missing criteria.
     - `run_matcher(listings, expired, facts, prefs, run_id, mode, ctx)`: creates application rows, checks hard rules (failed -> `skipped` with failed rule names and fit reason; passed -> `matched` with fit score and up to 2 gaps in `gaps` table). Wrapped in `@agent_span("matcher")`.
   - Created `backend/app/routers/matches.py`:
     - `GET /api/matches`: queries run applications, sorts non-skipped matches by `fit_score` descending, appends skipped matches at the end.
   - Created `backend/app/routers/gaps.py`:
     - `GET /api/gaps`: lists gaps for a run.
     - `POST /api/gaps/{gap_id}/answer`: creates vault fact with `P` ID, marks gap answered, returns `{"fact": Fact}`.
   - Registered all routers in `backend/app/main.py`.

---

## 2. Verification & Automated Test Results

39 automated unit tests pass offline with zero network dependencies:
```
tests/test_data.py ... [3 passed]
tests/test_db.py ..... [5 passed]
tests/test_flags.py . [1 passed]
tests/test_health.py .. [2 passed]
tests/test_intake.py .... [4 passed]
tests/test_llm.py ..... [5 passed]
tests/test_matcher.py ..... [5 passed]
tests/test_matches_gaps.py .. [2 passed]
tests/test_profile_router.py ... [3 passed]
tests/test_scout.py .. [2 passed]
tests/test_sensitive.py .... [4 passed]
tests/test_tracing.py ... [3 passed]
======================= 39 passed in 5.38s =======================
```
All quick checks (`python scripts/quick_check.py`) pass cleanly.

---

## 3. How to Verify by Hand

1. **Start the API server**:
   ```powershell
   python run_server.py
   ```
2. **Open Swagger UI**:
   Navigate to `http://localhost:8000/docs`.
3. **Load Demo Persona**:
   Call `POST /api/profile/load_demo`. Verify response status 201, fact counts (`cv`, `transcript`, `vault`), and that the family income fact has `sensitive: true`.
4. **Inspect Profile Facts**:
   Call `GET /api/profile/facts`. Verify returned fact IDs start with `C`, `T`, `P`.
5. **Add a Vault Fact**:
   Call `POST /api/profile/facts` with body `{"category": "projects", "text": "Built IoT monitor"}`. Verify returned ID starts with `P`.
6. **Query Matches**:
   Call `GET /api/matches`. Verify matches returned and sorted by fit score with skipped matches at the end.
7. **Query and Answer Gaps**:
   Call `GET /api/gaps`. Take a gap ID and call `POST /api/gaps/{id}/answer` with `{"text": "My policy experience..."}`. Verify gap is marked answered.
