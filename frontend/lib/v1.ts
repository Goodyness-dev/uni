import type { Application, ApplicationSummary, AppStatus, Fact, IntakeRequest, IntakeResponse, Match, Preferences, Run, VerificationReport } from "./types";

type Requester = <T>(path: string, options?: RequestInit) => Promise<T>;
interface Evidence extends Fact { document_id: string; source_excerpt: string }
interface Profile { personal_details: { preferences?: Preferences; _pending_facts?: Evidence[]; _verified_facts?: Evidence[] } }
interface NativeEvent { id: string; actor: string; event_type: string; created_at: string; payload: Record<string, unknown> }
interface NativeApplication {
  id: string; scholarship_id: string; status: string; created_at: string; scholarship_title?: string;
  confirmation_ref?: string; submitted_at?: string; events?: NativeEvent[];
  drafts?: { kind: string; version: number; content: string; source_facts: string[] }[];
  listing?: { id: string; name: string; provider: string; country: string; level?: string; deadline: string; source_url: string; ai_policy?: string; essay_prompt?: string; essay_word_limit?: number };
  verification?: VerificationReport; package?: Application["package"]; handoff?: Application["handoff"]; trace_url?: string;
}
interface NativeMatch { scholarship_id: string; fit_score: number; reasons: string[] }

export const useV1 = process.env.NEXT_PUBLIC_API_VERSION === "v1";

export function documentPreferences(facts: Fact[], current: Preferences): { preferences: Preferences; notes: string[] } {
  const text = facts.filter(fact => !fact.sensitive && fact.source !== "vault").map(fact => fact.text).join("\n");
  const preferences = { ...current, fields: [...current.fields] };
  const notes: string[] = [];
  const unique = (values: string[]): string | undefined => {
    const choices = [...new Set(values.map(value => value.trim()).filter(Boolean))];
    return choices.length === 1 ? choices[0] : undefined;
  };
  const email = unique(text.match(/[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g) ?? []);
  if (email && !preferences.email) preferences.email = email;
  const names = [...text.matchAll(/(?:Full name\s*:\s*|Transcript summary for\s+)([A-Z][\p{L}'-]+(?: [A-Z][\p{L}'-]+){1,3})(?=\s+(?:CGPA|GPA)|\n|$)/gu)].map(match => match[1]);
  if (email) {
    const parts = email.split("@")[0].split(".");
    if (parts.length >= 2 && parts.every(part => /^[A-Za-z]+$/.test(part))) {
      const pattern = new RegExp("\\b" + parts.join(" ") + "\\b", "i");
      const literal = text.match(pattern)?.[0];
      if (literal) names.push(literal);
    }
  }
  const name = unique(names);
  if (name && !preferences.full_name) preferences.full_name = name;
  const grades = [...text.matchAll(/\b(?:CGPA|GPA)\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(?:out of|\/)\s*(\d+(?:\.\d+)?)/gi)].map(match => `${Number(match[1])}/${Number(match[2])}`);
  const grade = unique(grades);
  if (grade) {
    const [gpa, scale] = grade.split("/").map(Number);
    if (gpa > 0 && gpa <= scale && scale > 0) {
      if (!preferences.gpa) { preferences.gpa = gpa; preferences.gpa_scale = scale; }
      else if (preferences.gpa !== gpa || preferences.gpa_scale !== scale) notes.push(`Your documents state GPA ${gpa}/${scale}; check the different value in your profile.`);
    }
  } else if (grades.length) notes.push("The documents contain conflicting GPA values. Confirm the correct value yourself.");
  const subject = unique([...text.matchAll(/\b(?:BSc|BEng|B\.Sc\.?|Bachelor of Science|Bachelor of Engineering)\s+(?:in\s+)?([A-Za-z][A-Za-z &-]{2,70})(?=,|\s+at\b)/gi)].map(match => match[1]));
  if (subject && !preferences.fields.length) { preferences.fields = [subject.toLowerCase()]; notes.push("Your documented subject is the starting study field; edit it if your target subject differs."); }
  const nationality = unique([...text.matchAll(/\bNationality\s*:\s*([A-Za-z]+)(?=\s|[,.;]|$)/gi)].map(match => match[1]));
  if (nationality && !preferences.nationality) preferences.nationality = nationality;
  return { preferences, notes };
}
const states: Record<string, AppStatus> = { discovered: "found", matched: "matched", researching: "researched", drafting: "tailored", ready_for_review: "ready", approved: "ready", submitting: "submitting", needs_human: "awaiting_user", submitted: "submitted", failed: "failed", withdrawn: "skipped", expired: "skipped" };
const status = (value: string): AppStatus => states[value] ?? "unconfirmed";
const demo = (url: string): boolean => { try { const parsed = new URL(url); return ["localhost", "127.0.0.1", "[::1]"].includes(parsed.hostname) && parsed.pathname.startsWith("/portal/"); } catch { return false; } };

export function createV1(send: Requester) {
  const reads = new Map<string, { until: number; value: Promise<unknown> }>();
  const request: Requester = async <T>(path: string, options: RequestInit = {}): Promise<T> => {
    if ((options.method ?? "GET") !== "GET") {
      reads.clear();
      return send<T>(path, options);
    }
    const prior = reads.get(path);
    if (prior && prior.until > Date.now()) return prior.value as Promise<T>;
    for (const [key, entry] of reads) if (entry.until <= Date.now()) reads.delete(key);
    const value = send<T>(path, options);
    reads.set(path, { until: Date.now() + 1200, value });
    try { return await value; }
    catch (error) { reads.delete(path); throw error; }
  };
  async function savePreferences(p: Preferences): Promise<void> {
    await request("/v1/profile", { method: "PUT", body: JSON.stringify({ personal_details: { full_name: p.full_name, nationalities: [p.nationality], target_level: p.level, preferences: p }, grades: { gpa: p.gpa, gpa_scale: p.gpa_scale }, target_countries: p.countries.map(country => country === "United Kingdom" ? "UK" : country), target_fields_of_study: p.fields }) });
  }
  async function getFacts(): Promise<{ facts: Fact[]; preferences: Preferences | null }> {
    const profile = await request<Profile>("/v1/profile");
    return { facts: [...(profile.personal_details._pending_facts ?? []), ...(profile.personal_details._verified_facts ?? [])].filter(fact => !fact.sensitive), preferences: profile.personal_details.preferences ?? null };
  }
  async function intake(input: IntakeRequest): Promise<IntakeResponse> {
    const p = input.preferences;
    if (!input.cv_text?.trim() && !input.cv_pdf_base64) {
      const prior = await getFacts();
      if (!prior.facts.some(fact => fact.source === "cv")) throw new Error("Provide a CV source before processing documents.");
      const hasContext = input.vault_text?.trim() || Object.values(input.vault_sections).some(value => value.trim()) || input.transcript_text?.trim() || input.transcript_pdf_base64;
      if (!hasContext) throw new Error("Your documents are already processed. Add missing context or select a replacement document before parsing again.");
    }
    await savePreferences(p);
    const encode = (text: string): string => { const bytes = new TextEncoder().encode(text); let binary = ""; for (const byte of bytes) binary += String.fromCharCode(byte); return btoa(binary); };
    const uploads = [
      { type: "cv", filename: input.cv_pdf_base64 ? "cv.pdf" : "cv.txt", content_base64: input.cv_pdf_base64 || (input.cv_text ? encode(input.cv_text) : "") },
      { type: "transcript", filename: input.transcript_pdf_base64 ? "transcript.pdf" : "transcript.txt", content_base64: input.transcript_pdf_base64 || (input.transcript_text ? encode(input.transcript_text) : "") },
      { type: "other", filename: "vault.txt", content_base64: encode([input.vault_text ?? "", ...Object.entries(input.vault_sections).filter(([category]) => category !== "hardships").map(([, value]) => value)].filter(Boolean).join(". ")) },
    ];
    for (const upload of uploads) if (upload.content_base64) await request("/v1/documents/upload", { method: "POST", body: JSON.stringify(upload) });
    const { facts } = await getFacts();
    return { facts, counts: { cv: facts.filter(f => f.source === "cv").length, transcript: facts.filter(f => f.source === "transcript").length, vault: facts.filter(f => f.source === "vault").length }, warnings: ["Review the extracted source facts before drafting. Review confirms source alignment, not document authenticity."] };
  }
  async function reviewPendingEvidence(): Promise<void> {
    const profile = await request<Profile>("/v1/profile");
    const groups = new Map<string, Evidence[]>();
    for (const fact of profile.personal_details._pending_facts ?? []) if (!fact.sensitive) groups.set(fact.document_id, [...(groups.get(fact.document_id) ?? []), fact]);
    for (const [id, facts] of groups) await request(`/v1/documents/${id}/verify`, { method: "POST", body: JSON.stringify({ confirmed: true, facts: facts.map(({ category, text, source_excerpt }) => ({ category, text, source_excerpt })) }) });
  }
  async function nativeApplications(runId?: string): Promise<NativeApplication[]> {
    const rows = await request<NativeApplication[]>("/v1/applications");
    if (!runId) return rows;
    const run = await request<Run>(`/v1/runs/${encodeURIComponent(runId)}`);
    return rows.filter(row => run.application_ids.includes(row.id));
  }
  async function getApplication(id: string): Promise<Application> {
    const row = await request<NativeApplication>(`/v1/applications/${encodeURIComponent(id)}`);
    const listing = row.listing;
    const event = row.events?.find(e => e.event_type === "status_changed_matched");
    const verificationEvent = [...(row.events ?? [])].reverse().find(e => e.event_type === "verification_report");
    const researchEvent = [...(row.events ?? [])].reverse().find(e => e.event_type === "research_evidence");
    const research = researchEvent?.payload.facts as { fact_id: string; category: string; claim: string; source_url: string; retrieved_at: string }[] | undefined;
    const essay = [...(row.drafts ?? [])].filter(d => d.kind === "essay").sort((a, b) => b.version - a.version)[0];
    const sourceFacts = essay ? (await getFacts()).facts.filter(fact => (essay.source_facts.includes(fact.text) || essay.source_facts.includes(fact.id))) : [];
    const angleEvent = [...(row.events ?? [])].reverse().find(e => e.event_type === "source_angles");
    const angles = (angleEvent?.payload.angles ?? []) as { angle_id: string; supporting_profile_facts: string[]; reasoning: string; score: number }[];
    const edges = angles.flatMap(angle => {
      const ids = sourceFacts.filter(fact => angle.supporting_profile_facts.includes(fact.text)).map(fact => fact.id);
      return ids.length ? [{ id: angle.angle_id, profile_fact_ids: ids, dossier_fact_ids: [], reason: angle.reasoning, use_in: "cv_bullet" as const, strength: angle.score, selected: true }] : [];
    });
    const extractive = (row.verification as (VerificationReport & { mode?: string }) | undefined)?.mode === "extractive";
    const sourceSegments = verificationEvent?.payload.segments as { text: string; source_ids: string[]; section: string }[] | undefined;
    const section = (name: string) => (sourceSegments ?? []).filter(s => s.section === name).map(s => ({ text: s.text, source_ids: s.source_ids, status: "supported" as const }));
    const manual = listing && (!demo(listing.source_url) || !["allowed", "disclose"].includes(listing.ai_policy ?? "unknown"));
    return { id: row.id, run_id: "", listing: listing ? { ...listing, is_mock: demo(listing.source_url), channel: manual ? "package_only" : "portal_form", ai_policy: listing.ai_policy ?? "unknown", essay_prompt: listing.essay_prompt ?? "", essay_word_limit: listing.essay_word_limit ?? 0 } : null,
      status: manual && ["ready_for_review", "approved"].includes(row.status) ? "prepared" : status(row.status), fit_score: typeof event?.payload.fit_score === "number" ? event.payload.fit_score : null, fit_reason: null, failure_reason: null,
      dossier: researchEvent ? { listing_id: row.scholarship_id, facts: (research ?? []).map(fact => ({ id: fact.fact_id, topic: fact.category, text: fact.claim, source_url: fact.source_url, snippet: fact.claim, retrieved_at: fact.retrieved_at })), degraded: !research?.length } : null, edges, tailored: essay ? { cv_summary: section("cv_summary"), cv_bullets: extractive ? sourceFacts.map(fact => ({ text: fact.text, source_ids: [fact.id], status: "supported" as const })) : section("cv_bullets"), essay: extractive ? [{ text: essay.content, source_ids: sourceFacts.map(fact => fact.id), status: "supported" }] : section("essay"), mode: sourceSegments?.length || extractive ? "full" : "notes_only", outline: sourceSegments?.length || extractive ? [] : [essay.content] } : null,
      verification: row.verification ?? null, package: row.package ?? null, handoff: row.handoff ?? null,
      submission: { confirmed: row.status === "submitted" && !!row.confirmation_ref, confirmation_code: row.confirmation_ref ?? null, channel: manual ? "package_only" : "portal_form", at: row.submitted_at ?? null }, notifications: [],
      timeline: (row.events ?? []).map((e, i) => ({ event_no: i + 1, at: e.created_at, run_id: "", application_id: row.id, agent: e.actor, type: e.event_type, message: typeof e.payload.message === "string" ? e.payload.message : typeof e.payload.reason === "string" ? e.payload.reason : e.event_type.replaceAll("_", " "), data: e.payload })), trace_url: row.trace_url ?? null, metrics: null };
  }
  async function getApplications(runId?: string): Promise<{ applications: ApplicationSummary[] }> {
    const rows = await nativeApplications(runId);
    const details = await Promise.all(rows.map(row => request<NativeApplication>(`/v1/applications/${row.id}`)));
    return { applications: details.map(detail => {
      const listing = detail.listing;
      const ownedDemo = !!listing && demo(listing.source_url);
      const manual = !ownedDemo || !["allowed", "disclose"].includes(listing?.ai_policy ?? "unknown");
      const matched = detail.events?.find(event => event.event_type === "status_changed_matched");
      return { id: detail.id, listing_id: detail.scholarship_id, name: listing?.name ?? detail.scholarship_title ?? "", is_mock: ownedDemo, status: manual && ["ready_for_review", "approved"].includes(detail.status) ? "prepared" : status(detail.status), channel: manual ? "package_only" : "portal_form", fit_score: typeof matched?.payload.fit_score === "number" ? matched.payload.fit_score : null, deadline: listing?.deadline ?? "", updated_at: detail.created_at };
    }) };
  }
  async function getMatches(runId?: string): Promise<{ matches: Match[] }> {
    const rows = await nativeApplications(runId);
    const matches = await request<NativeMatch[]>("/v1/matches");
    const details = await Promise.all(rows.map(row => request<NativeApplication>(`/v1/applications/${row.id}`)));
    return { matches: details.flatMap(row => { const match = matches.find(m => m.scholarship_id === row.scholarship_id); const listing = row.listing; if (!match || !listing) return []; return [{ application_id: row.id, listing_id: row.scholarship_id, name: listing.name, is_mock: demo(listing.source_url), country: listing.country, level: listing.level ?? "", deadline: listing.deadline, channel: demo(listing.source_url) ? "portal_form" as const : "package_only" as const, fit_score: match.fit_score, fit_reason: match.reasons.join("; "), status: status(row.status), hard_rule_results: { country: null, level: null, gpa: null, field: null, deadline: null, nationality: null }, failed_rules: [] }]; }) };
  }
  return { intake, savePreferences, getFacts, reviewPendingEvidence, getApplication, getApplications, getMatches };
}
