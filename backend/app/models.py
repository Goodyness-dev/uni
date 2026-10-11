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
