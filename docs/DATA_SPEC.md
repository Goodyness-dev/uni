# DATA_SPEC.md

All data shapes used inside the backend. The API shapes seen by the frontend are in `ARCHITECTURE.md` section 9. Keep both consistent.

## 1. Conventions

1. Dates are strings `YYYY/MM/DD`. Date times are `YYYY/MM/DD HH:MM:SS` in UTC. Parse with `datetime.strptime`. Never store other formats.
2. Ids: facts `C1`, `T1`, `P1`; dossier facts `D1`; edges `E1`; claims `CL1`; gaps `G1`; applications `app_1`; runs `run_YYYYMMDD_NNN` (digits only plus underscores).
3. All text columns are UTF 8. All JSON columns store `json.dumps` output.
4. IDs for facts are stable per profile. If a fact is edited, keep its id.

## 2. SQLite tables (create in `db.py`)

```
CREATE TABLE IF NOT EXISTS facts (
  id TEXT PRIMARY KEY,
  source TEXT NOT NULL,
  category TEXT NOT NULL,
  text TEXT NOT NULL,
  sensitive INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
  id TEXT PRIMARY KEY,
  mode TEXT NOT NULL,
  status TEXT NOT NULL,
  top_n INTEGER NOT NULL,
  live_research INTEGER NOT NULL DEFAULT 0,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  metrics_json TEXT,
  neatlogs_url TEXT
);

CREATE TABLE IF NOT EXISTS applications (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  listing_id TEXT NOT NULL,
  status TEXT NOT NULL,
  channel TEXT NOT NULL,
  fit_score INTEGER,
  fit_reason TEXT,
  hard_rules_json TEXT,
  failure_reason TEXT,
  dossier_json TEXT,
  edges_json TEXT,
  tailored_json TEXT,
  verification_json TEXT,
  package_json TEXT,
  handoff_json TEXT,
  submission_json TEXT,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
  event_no INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL,
  application_id TEXT,
  at TEXT NOT NULL,
  agent TEXT NOT NULL,
  type TEXT NOT NULL,
  message TEXT NOT NULL,
  data_json TEXT
);

CREATE TABLE IF NOT EXISTS notifications (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT,
  application_id TEXT,
  text TEXT NOT NULL,
  channel TEXT NOT NULL,
  sent INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS gaps (
  id TEXT PRIMARY KEY,
  application_id TEXT NOT NULL,
  criterion TEXT NOT NULL,
  question TEXT NOT NULL,
  answered INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS portal_drafts (
  draft_id TEXT PRIMARY KEY,
  listing_id TEXT NOT NULL,
  fields_json TEXT NOT NULL,
  submitted INTEGER NOT NULL DEFAULT 0,
  confirmation_code TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS failure_flags (
  name TEXT PRIMARY KEY,
  enabled INTEGER NOT NULL DEFAULT 0
);
```

Allowed values: `facts.source` is cv, transcript or vault. `runs.mode` is A, B or Z. `runs.status` is running, completed, failed or interrupted. `portal` channel values are listed in section 3.

## 3. Listings file (`backend/data/listings.json`)

Top level is an object with a `listings` array. Each listing:

```
{
  "id": "mock_portal_masters",
  "name": "Demo Portal Masters Award",
  "is_mock": true,
  "provider": "Demo University",
  "country": "UK",
  "level": "masters",
  "fields": ["computer engineering", "computer science", "artificial intelligence"],
  "min_gpa": 4.0,
  "gpa_scale": 5.0,
  "eligible_nationalities": ["Nigeria", "Ghana", "Kenya"],
  "deadline": "2026/12/01",
  "deadline_note": "",
  "funding": "full",
  "channel": "portal_form",
  "submission": {"portal_path": "/portal/apply/mock_portal_masters", "email": ""},
  "criteria_text": "Short paragraph copied from the listing page describing what the committee looks for.",
  "essay_prompt": "In 300 words, describe how your work will benefit your community.",
  "essay_word_limit": 300,
  "required_documents": ["cv", "essay"],
  "source_url": "https://example.org/official",
  "copied_on": "2026/10/10"
}
```

Channel values: `email`, `portal_form` (demo portal, CAPTCHA optional through the flag), `portal_captcha` (demo portal with the CAPTCHA always on), `package_only` (all real listings).

The 5 listings:
1. Three REAL listings (`is_mock` false, `channel` `package_only`). Choose three programs genuinely open to Nigerian applicants (candidates to consider: Chevening, Commonwealth Master's scholarships, Mastercard Foundation Scholars Program). Copy the eligibility, deadline and essay prompt BY HAND from each official page. Record `source_url` and `copied_on`. If the current cycle deadline has passed, put the next expected deadline and explain in `deadline_note`. Do not guess any detail. If a detail is not on the page, leave it empty.
2. `mock_portal_masters` (`is_mock` true, `channel` `portal_form`): submits through the demo portal over HTTP. The CAPTCHA appears when the `captcha_wall` flag is on.
3. `mock_email_award` (`is_mock` true, `channel` `email`): sends the application by email to `DEMO_INBOX_EMAIL`.
Label mock listings "DEMO LISTING" in the UI.

## 4. Synthetic persona (`backend/data/synthetic/`)

Create a fictional applicant. Never use a real person. Files:
1. `cv.txt`: plain text CV.
2. `transcript.txt`: courses and grades.
3. `preferences.json`: in the shape from `ARCHITECTURE.md` 9.2.
4. `vault.json`: Vault sections in the shape from 9.2, with plenty of detail.

Persona outline (adjust names but keep it fictional): Tobi Adeyemi, BSc Computer Engineering from a Nigerian university, CGPA 4.3 out of 5.0, graduated 2025, one internship, a final year project on low cost solar monitoring with a microcontroller, taught coding to secondary school students for 200 hours as a volunteer, captained the university football team for 2 seasons, organized a campus hackathon with 120 participants, a few certifications, speaks English and Yoruba, wants a Master's in AI for energy systems.

Required traps for the demo (these make the verification story real):
1. The CV does NOT mention a leadership title in the tech club, but the Vault says Tobi was "assistant coordinator". The Tailor must not upgrade this to "president".
2. No professional experience longer than 6 months. The Tailor must not claim "years of experience".
3. One scholarship criterion (for example public policy exposure) has no matching fact, which creates a gap question.
4. One sensitive fact in the Vault (marked `sensitive`: true, for example a family income detail) must never appear in any output.

## 5. Dossier cache (`backend/data/dossier_cache/{listing_id}.json`)

```
{
  "listing_id": "mock_portal_masters",
  "retrieved_at": "2026/10/10 14:20:00",
  "facts": [
    {"id": "D1", "topic": "program_focus", "text": "...", "source_url": "https://...", "snippet": "short excerpt, under 25 words"}
  ],
  "people": [
    {"name": "Prof. Example", "role": "Programme director", "research_areas": ["..."], "source_url": "https://...", "snippet": "..."}
  ],
  "scholarship_priorities": [
    {"id": "D9", "text": "...", "source_url": "https://...", "snippet": "..."}
  ]
}
```
Rules: every entry needs a `source_url` and a `snippet`. No source means it does not go in the file. For mock listings, write the dossier pages yourself as small static pages hosted by the demo portal (`/portal/about/{listing_id}`) so the source URLs are real and the facts are honestly about a fictional school. Label them as demo content.

## 6. Matcher output

```
{"application_id": "app_1", "listing_id": "...", "hard_rule_results": {"country": true, "level": true, "gpa": true, "field": true, "deadline": true, "nationality": true}, "fit_score": 87, "fit_reason": "one sentence"}
```
A listing failing any hard rule gets status `skipped` with the failed rule names as the reason. GPA comparison must normalize scales (`gpa / gpa_scale`).

## 7. Edge, claim and segment objects

Edge, Segment and VerificationReport shapes are in `ARCHITECTURE.md` 9.5. Additional internal fields:
1. `Edge.threshold`: selection keeps edges with `strength` of at least 0.6, maximum 3 per application.
2. `Claim` fields: `id`, `text`, `source_ids`, `verdict`, `reason`, `deterministic_pass` (bool), `llm_pass` (bool).
3. A claim is `supported` only if `deterministic_pass` AND `llm_pass` are true.

Deterministic check definition: for each claim, extract numbers (digits, years, percentages), proper nouns and quoted terms with a simple regex. Each extracted item must appear (case insensitive) in at least one cited source text. Words like "approximately" are not checked. If a claim has no cited source ids, `deterministic_pass` is false.

## 8. Telegram message templates

Keep each message under 400 characters. Use plain text.

1. Matches found: `ScholarPilot: found {n} scholarships you qualify for. Top match: {name} (fit {score}). Researching the top {top_n} now.`
2. Researched: `Researched {name}: {k} sourced facts about the program. Looking for your strongest evidence.`
3. Edges used: `Used {fact_id} ({short fact}) because {reason}.` (one line per edge, max 3)
4. Verified: `Verified your {name} application: {supported} claims supported, {removed} removed as unsupported.`
5. Submitted: `Submitted {name}. Confirmation: {code}.`
6. Prepared: `{name} needs manual submission. Your package is ready: {frontend_url}/applications/{id}`
7. Handoff: `{name} needs you for a quick CAPTCHA. Open {frontend_url}/handoff/{id}, solve it, then tap Done.` with inline buttons Done and Open.
8. Failed: `{name} failed at {step}: {reason}. The agent will not retry automatically.`
9. Deadline: `{name} deadline is in {hours} hours and its status is {status}.`
10. Gap question: `Optional question for {name}: {question} Reply in the app to add it to your profile.`

## 9. Failure flags

Names: `llm_429`, `bad_json`, `portal_500`, `captcha_wall`. Stored in `failure_flags`. Implementation in `failure_flags.py`:

1. `llm_429`: the primary LLM wrapper raises a simulated rate limit error on the next 2 calls to the primary model, then clears itself. The wrapper must then retry and fall back to the secondary model. Log `failure_injected` and `llm_fallback` events.
2. `bad_json`: the next LLM call that expects JSON returns a truncated string. The wrapper must run the repair path. Log `failure_injected` and `json_repair` events.
3. `portal_500`: the portal submit endpoint returns HTTP 500 for the next 3 calls. The Applier must retry 3 times then use the email fallback or `prepared`.
4. `captcha_wall`: the portal form shows the challenge and the submit endpoint requires `captcha_answer`. The Applier must detect the blocker, hand off, and resume after Done.

Injected failures are for demonstration and testing only. They must be visibly logged as injected so the evidence is honest.

## 10. Sensitive filter

`sensitive.py` marks a fact as sensitive if its category is in `health`, `religion`, `disability`, `family_income`, `immigration`, or if the user marked it sensitive in the form. The function `strip_sensitive(facts, listing, consent)` returns the facts allowed in prompts. A sensitive fact is allowed only if the listing has `requires_sensitive` listing a matching category AND `consent` is true. Write unit tests for this function before using it.
