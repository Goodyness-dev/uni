export type SourceKind = "cv" | "transcript" | "vault";
export type Channel = "email" | "portal_form" | "portal_captcha" | "package_only";
export type AppStatus =
  | "found" | "matched" | "skipped" | "researched" | "edges_selected" | "tailored"
  | "verified" | "ready" | "submitting" | "awaiting_user" | "submitted"
  | "prepared" | "unconfirmed" | "failed";
export type RunStatus = "running" | "completed" | "failed" | "interrupted";

export interface Fact {
  id: string;
  source: SourceKind;
  category: string;
  text: string;
  sensitive: boolean;
}

export interface Preferences {
  full_name: string;
  email: string;
  level: "undergraduate" | "masters" | "phd";
  fields: string[];
  countries: string[];
  funding: "full" | "partial";
  start_year: number;
  nationality: string;
  gpa: number;
  gpa_scale: number;
  sensitive_consent: boolean;
}

export interface IntakeRequest {
  cv_text?: string;
  cv_pdf_base64?: string;
  transcript_text?: string;
  transcript_pdf_base64?: string;
  preferences: Preferences;
  vault_sections: Record<string, string>;
  vault_text?: string;
}

export interface IntakeResponse {
  facts: Fact[];
  counts: { cv: number; transcript: number; vault: number };
  warnings: string[];
}

export interface HardRuleResults {
  country: boolean | null;
  level: boolean | null;
  gpa: boolean | null;
  field: boolean | null;
  deadline: boolean | null;
  nationality: boolean | null;
}

export interface Match {
  application_id: string;
  listing_id: string;
  name: string;
  is_mock: boolean;
  country: string;
  level: string;
  deadline: string;
  channel: Channel;
  fit_score: number;
  fit_reason: string;
  status: AppStatus;
  hard_rule_results: HardRuleResults;
  failed_rules: string[];
}

export interface DossierFact {
  id: string;
  topic: string;
  text: string;
  source_url: string;
  snippet: string;
  retrieved_at: string;
}

export interface Dossier {
  listing_id: string;
  facts: DossierFact[];
  degraded: boolean;
}

export interface Edge {
  id: string;
  profile_fact_ids: string[];
  dossier_fact_ids: string[];
  reason: string;
  use_in: "cv_bullet" | "essay_opening" | "essay_body" | "attachment";
  strength: number;
  selected: boolean;
}

export interface Segment {
  text: string;
  source_ids: string[];
  status: "supported" | "removed" | "flagged";
}

export interface TailoredOutput {
  cv_summary: Segment[];
  cv_bullets: Segment[];
  essay: Segment[];
  mode: "full" | "notes_only";
  outline: string[];
}

export interface Claim {
  id: string;
  text: string;
  segment_index: number;
  section: "cv_summary" | "cv_bullets" | "essay";
  source_ids: string[];
  verdict: "supported" | "unsupported" | "partial";
  reason: string;
  deterministic_pass: boolean;
  llm_pass: boolean;
  challenged: boolean;
  overturned: boolean;
}

export interface RemovedClaim {
  text: string;
  reason: string;
}

export interface VerificationReport {
  rounds: number;
  claims: Claim[];
  removed_claims: RemovedClaim[];
  overturned_claims: RemovedClaim[];
  unsupported_before: number;
  unsupported_final: number;
}

export interface AppEvent {
  event_no: number;
  at: string;
  run_id: string;
  application_id: string | null;
  agent: string;
  type: string;
  message: string;
  data: Record<string, unknown>;
}

export interface RunMetrics {
  tokens_total: number;
  cost_usd: number;
  latency_seconds: number;
  claims_total: number;
  claims_unsupported: number;
  claims_removed: number;
  claims_overturned: number;
  personal_refs_total: number;
  personal_refs_sourced: number;
  llm_calls: number;
  llm_fallbacks: number;
  retries: number;
  recovery_decisions: number;
  crustdata_credits: number;
}

export interface Run {
  run_id: string;
  mode: "A" | "B" | "Z";
  status: RunStatus;
  started_at: string;
  finished_at: string | null;
  application_ids: string[];
  metrics: RunMetrics | null;
  trace_url: string | null;
}

export interface ApplicationSummary {
  id: string;
  listing_id: string;
  name: string;
  is_mock: boolean;
  status: AppStatus;
  channel: Channel;
  fit_score: number | null;
  deadline: string;
  updated_at: string;
}

export interface Handoff {
  reason: string;
  portal_url: string;
  instructions: string;
}

export interface Application {
  id: string;
  run_id: string;
  listing: {
    id: string;
    name: string;
    is_mock: boolean;
    provider: string;
    country: string;
    deadline: string;
    channel: Channel;
    ai_policy: string;
    source_url: string;
    essay_prompt: string;
    essay_word_limit: number;
  } | null;
  status: AppStatus;
  fit_score: number | null;
  fit_reason: string | null;
  failure_reason: string | null;
  dossier: Dossier | null;
  edges: Edge[];
  tailored: TailoredOutput | null;
  verification: VerificationReport | null;
  package: { cv_pdf_url: string; essay_url: string; checklist_url: string } | null;
  handoff: Handoff | null;
  submission: { confirmed: boolean; confirmation_code: string | null; channel: string; at: string | null };
  notifications: { at: string; text: string; sent: boolean }[];
  timeline: AppEvent[];
  trace_url: string | null;
  metrics: RunMetrics | null;
}

export interface Gap {
  id: string;
  application_id: string;
  criterion: string;
  question: string;
  answered: boolean;
}

export interface HealthResponse {
  status: string;
  llm_primary: "configured" | "missing";
  llm_fallback: "configured" | "missing";
  telegram: "configured" | "missing";
  neatlogs: "configured" | "missing";
  smtp: "configured" | "missing";
  crustdata: "configured" | "missing";
  demo_mode: boolean;
}

export interface FailureFlags {
  llm_429: boolean;
  bad_json: boolean;
  portal_500: boolean;
  captcha_wall: boolean;
  research_down: boolean;
  smtp_fail: boolean;
  injection_page: boolean;
}

export interface FailureFlagsResponse {
  flags: FailureFlags;
}
