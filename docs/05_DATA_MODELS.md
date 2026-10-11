# 05_DATA_MODELS.md

Exact data shapes. Put the Pydantic models in `backend/app/models.py` exactly as written (imports at the top). The frontend types in `frontend/lib/types.ts` mirror them.

## 1. models.py (copy this)

```python
from typing import Optional, Literal
from pydantic import BaseModel, Field

SourceKind = Literal["cv", "transcript", "vault"]
Mode = Literal["A", "B", "Z"]
Channel = Literal["email", "portal_form", "portal_captcha", "package_only"]
AiPolicy = Literal["allowed", "disclose", "restricted", "unknown"]
AppStatus = Literal[
    "found", "matched", "skipped", "researched", "edges_selected", "tailored",
    "verified", "ready", "submitting", "awaiting_user", "submitted",
    "prepared", "unconfirmed", "failed",
]
UseIn = Literal["cv_bullet", "essay_opening", "essay_body", "attachment"]
SegmentStatus = Literal["supported", "removed", "flagged"]
Verdict = Literal["supported", "unsupported", "partial"]


class Fact(BaseModel):
    id: str
    source: SourceKind
    category: str
    text: str
    sensitive: bool = False


class Preferences(BaseModel):
    full_name: str = "Applicant"
    email: str = ""
    level: Literal["undergraduate", "masters", "phd"] = "masters"
    fields: list[str] = Field(default_factory=list)
    countries: list[str] = Field(default_factory=list)
    funding: Literal["full", "partial"] = "full"
    start_year: int = 2027
    nationality: str = "Nigeria"
    gpa: float = 0.0
    gpa_scale: float = 5.0
    sensitive_consent: bool = False


class Listing(BaseModel):
    id: str
    name: str
    is_mock: bool
    provider: str
    country: str
    level: str
    fields: list[str]
    min_gpa: float = 0.0
    gpa_scale: float = 5.0
    eligible_nationalities: list[str] = Field(default_factory=list)
    deadline: str
    deadline_note: str = ""
    funding: str = "full"
    channel: Channel
    ai_policy: AiPolicy = "allowed"
    portal_path: str = ""
    email: str = ""
    criteria_text: str
    essay_prompt: str
    essay_word_limit: int = 300
    required_documents: list[str] = Field(default_factory=lambda: ["cv", "essay"])
    requires_sensitive: list[str] = Field(default_factory=list)
    source_url: str = ""
    copied_on: str = ""


class HardRuleResults(BaseModel):
    country: bool
    level: bool
    gpa: bool
    field: bool
    deadline: bool
    nationality: bool


class Match(BaseModel):
    application_id: str
    listing_id: str
    name: str
    is_mock: bool
    country: str
    level: str
    deadline: str
    channel: Channel
    fit_score: int
    fit_reason: str
    status: AppStatus
    hard_rule_results: HardRuleResults
    failed_rules: list[str] = Field(default_factory=list)


class DossierFact(BaseModel):
    id: str
    topic: str
    text: str
    source_url: str
    snippet: str
    retrieved_at: str


class Dossier(BaseModel):
    listing_id: str
    facts: list[DossierFact] = Field(default_factory=list)
    degraded: bool = False


class Edge(BaseModel):
    id: str
    profile_fact_ids: list[str]
    dossier_fact_ids: list[str]
    reason: str
    use_in: UseIn
    strength: float
    selected: bool = False


class Segment(BaseModel):
    text: str
    source_ids: list[str] = Field(default_factory=list)
    status: SegmentStatus = "supported"


class TailoredOutput(BaseModel):
    cv_summary: list[Segment] = Field(default_factory=list)
    cv_bullets: list[Segment] = Field(default_factory=list)
    essay: list[Segment] = Field(default_factory=list)
    mode: Literal["full", "notes_only"] = "full"
    outline: list[str] = Field(default_factory=list)


class Claim(BaseModel):
    id: str
    text: str
    segment_index: int
    section: Literal["cv_summary", "cv_bullets", "essay"]
    source_ids: list[str] = Field(default_factory=list)
    verdict: Verdict = "unsupported"
    reason: str = ""
    deterministic_pass: bool = False
    llm_pass: bool = False
    challenged: bool = False
    overturned: bool = False


class RemovedClaim(BaseModel):
    text: str
    reason: str


class VerificationReport(BaseModel):
    rounds: int = 0
    claims: list[Claim] = Field(default_factory=list)
    removed_claims: list[RemovedClaim] = Field(default_factory=list)
    overturned_claims: list[RemovedClaim] = Field(default_factory=list)
    unsupported_before: int = 0
    unsupported_final: int = 0


class Event(BaseModel):
    event_no: int
    at: str
    run_id: str
    application_id: Optional[str] = None
    agent: str
    type: str
    message: str
    data: dict = Field(default_factory=dict)


class RunMetrics(BaseModel):
    tokens_total: int = 0
    cost_usd: float = 0.0
    latency_seconds: float = 0.0
    claims_total: int = 0
    claims_unsupported: int = 0
    claims_removed: int = 0
    claims_overturned: int = 0
    personal_refs_total: int = 0
    personal_refs_sourced: int = 0
    llm_calls: int = 0
    llm_fallbacks: int = 0
    retries: int = 0
    recovery_decisions: int = 0
    crustdata_credits: int = 0


class LLMResult(BaseModel):
    parsed: dict
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    latency_seconds: float = 0.0
    model: str = ""
    fallback_used: bool = False
    attempts: int = 1
    json_repaired: bool = False
```

Notes for the coding agent:
1. `LLMResult.parsed` holds the dict returned by the model after validation. Agents convert it into the specific model with `Model(**parsed)` or `Model.model_validate(parsed)`.
2. Do not rename fields. The API contract uses these names exactly.
3. A plain class `RunContext` (a dataclass with `run_id: str`, `app_id: Optional[str]`, `mode: str`, `listing_id: Optional[str]`) lives in `app/errors.py` next to the error classes, imported everywhere that needs trace metadata.

## 2. SQLite schema (db.py creates these with `CREATE TABLE IF NOT EXISTS`)

```sql
CREATE TABLE IF NOT EXISTS facts (
  id TEXT PRIMARY KEY,
  source TEXT NOT NULL,
  category TEXT NOT NULL,
  text TEXT NOT NULL,
  sensitive INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS preferences (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  json TEXT NOT NULL
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
  trace_url TEXT
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
  failed_rules_json TEXT,
  failure_reason TEXT,
  dossier_json TEXT,
  edges_json TEXT,
  tailored_json TEXT,
  verification_json TEXT,
  package_json TEXT,
  handoff_json TEXT,
  submission_json TEXT,
  metrics_json TEXT,
  trace_url TEXT,
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
  channel TEXT NOT NULL,
  text TEXT NOT NULL,
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
  idempotency_key TEXT,
  fields_json TEXT NOT NULL,
  submitted INTEGER NOT NULL DEFAULT 0,
  confirmation_code TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS failure_flags (
  name TEXT PRIMARY KEY,
  enabled INTEGER NOT NULL DEFAULT 0,
  remaining INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS poller_state (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  last_update_id INTEGER NOT NULL DEFAULT 0
);
```

Seed `failure_flags` with rows for `llm_429`, `bad_json`, `portal_500`, `captcha_wall`, `research_down`, `smtp_fail`, `injection_page` (all disabled, remaining 0).

## 3. Application row to API mapping

`applications.*_json` columns hold: `dossier_json` a `Dossier`, `edges_json` a list of `Edge`, `tailored_json` a `TailoredOutput`, `verification_json` a `VerificationReport`, `package_json` an object `{"cv_pdf": path, "essay_txt": path, "checklist_txt": path}` with file paths relative to `backend/data/packages/`, `handoff_json` an object `{"reason": ..., "portal_url": ..., "draft_id": ..., "instructions": ...}` or null, `submission_json` an object `{"confirmed": bool, "confirmation_code": str or null, "channel": str, "at": str or null}`.

## 4. Listings file (`backend/data/listings.json`)

Top level: `{"listings": [Listing, ...]}`. Five entries: 2 real and 3 mock (see `11_DEMO_PORTAL_AND_SYNTHETIC_DATA.md` for exact content). Validate the file with the `Listing` model at startup and fail loudly with the entry id when one is invalid.

## 5. Dossier cache file (`backend/data/dossier_cache/{listing_id}.json`)

```json
{
  "listing_id": "mock_portal_masters",
  "retrieved_at": "2026/10/10 14:20:00",
  "facts": [
    {"id": "D1", "topic": "program_focus", "text": "...", "source_url": "http://localhost:8000/portal/about/mock_portal_masters", "snippet": "short excerpt from the page text", "retrieved_at": "2026/10/10 14:20:00"}
  ]
}
```
Fact ids are `D1`, `D2` and so on within the file. At load time the Researcher prefixes nothing (ids are unique per listing, edges reference ids together with the listing context).

## 6. Event types (the `type` field of events)

`status_changed`, `retry`, `llm_fallback`, `json_repair`, `recovery_decision`, `claim_removed`, `claim_overturned`, `blocker_detected`, `handoff_sent`, `submission_confirmed`, `notification_sent`, `failure_injected`, `research_used_cache`, `edge_selected`, `gap_created`, `run_started`, `run_completed`, `run_interrupted`, `step_started`, `step_completed`.

Agent names used in events: `coordinator`, `intake`, `scout`, `matcher`, `researcher`, `edge_finder`, `tailor`, `verifier`, `challenger`, `applier`, `packager`, `notifier`, `portal`.

## 7. Telegram message templates (under 400 characters, plain text)

1. `matches_found`: `ScholarPilot: found {n} scholarships you qualify for. Top match: {name} (fit {score}). Researching the top {top_n} now.`
2. `researched`: `Researched {name}: {k} sourced facts about the programme. Looking for your strongest evidence.`
3. `edges_used`: `Used {fact_id} ({short_fact}) because {reason}.` One line per selected edge, at most 3 lines in one message.
4. `verified`: `Verified {name}: {supported} claims supported, {removed} removed, {overturned} overturned by self challenge.`
5. `submitted`: `Submitted {name}. Confirmation: {code}.`
6. `prepared`: `{name} needs manual submission. Your package is ready: {frontend_url}/applications/{id}`
7. `handoff`: `{name} needs you for a quick CAPTCHA. Open {frontend_url}/handoff/{id}, solve it, then tap Done.` Sent with an inline keyboard: a Done button with callback data `done:{application_id}` and a link button Open.
8. `failed`: `{name} failed at {step}: {reason}.`
9. `gap`: `Optional question for {name}: {question} Answer it in the app to add it to your profile.`
10. `restricted_briefing`: see `07_AGENTS_SPEC.md` section 9.

Each template is a function in `notify.py` that returns the string. Keep wording exactly.

## 8. Metrics definitions (so run A and B are comparable)

Computed per run by summing over applications that reached verification:
1. `claims_total`: number of claims extracted in the FIRST audit of each application.
2. `claims_unsupported`: claims with verdict `unsupported` or `partial` in the FIRST audit (before any enforcement). This is the headline number for the comparison.
3. `claims_removed`: claims removed at the end of enforcement (0 in mode A).
4. `claims_overturned`: claims overturned by the Challenger.
5. `unsupported_final`: unsupported claims remaining in the final output (target 0 in mode B).
6. `personal_refs_total` and `personal_refs_sourced`: segments in the essay that refer to the school or programme, and how many of them carry a dossier fact id.
7. Tokens, cost, latency, llm calls, fallbacks, retries and recovery decisions: summed from `LLMResult` and events.
