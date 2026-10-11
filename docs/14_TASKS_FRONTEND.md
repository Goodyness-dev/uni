# 14_TASKS_FRONTEND.md

Frontend task cards for Ayo. Read `15_DESIGN_BRIEF.md` for the product, screens and design tokens. This file gives the exact technical specs so Antigravity does not guess. Data shapes come from `06_API_CONTRACT.md` and `05_DATA_MODELS.md`.

Use one Antigravity CLI conversation per card with the master prompt from `12_ANTIGRAVITY_RULES.md` section 6.1, replacing the task id. Only edit `frontend/` (and the portal templates in F07).

Environment (`frontend/.env.local`, gitignored):
```
NEXT_PUBLIC_API_BASE=http://localhost:8000
NEXT_PUBLIC_USE_MOCKS=true
```

## Fixed technical decisions

1. Next.js app router, TypeScript strict, Tailwind. No extra libraries (no axios, no swr, no state library, no component library). Icons: if you want icons, install only the lucide icon package for React, nothing else.
2. Routes: `/` (Upload and Profile), `/matches`, `/applications/[id]`, `/handoff/[id]`.
3. All data access through `frontend/lib/api.ts`. Pages never call `fetch` directly.
4. Client components for any page that polls (`"use client"` at the top).
5. The latest run id is read from `GET /api/runs/latest`, so no global state is needed. After pressing Run agent, navigate to `/matches`.
6. Dates arrive as strings (`YYYY/MM/DD` and `YYYY/MM/DD HH:MM:SS` in UTC). Parse with the helper in `lib/format.ts`.

## F01. [x] Types, API client, mocks

Goal: the typed foundation and mock data so every screen can be built without the backend.
Depends: S10. Time box: 45 min.
Create:
1. `frontend/lib/types.ts` with exactly the types below.
2. `frontend/lib/api.ts` (section F01 api spec below).
3. `frontend/lib/format.ts`.
4. `frontend/mocks/` JSON files (list below).

`types.ts` (copy):
```ts
export type SourceKind = "cv" | "transcript" | "vault";
export type Channel = "email" | "portal_form" | "portal_captcha" | "package_only";
export type AppStatus =
  | "found" | "matched" | "skipped" | "researched" | "edges_selected" | "tailored"
  | "verified" | "ready" | "submitting" | "awaiting_user" | "submitted"
  | "prepared" | "unconfirmed" | "failed";
export type RunStatus = "running" | "completed" | "failed" | "interrupted";

export interface Fact { id: string; source: SourceKind; category: string; text: string; sensitive: boolean; }
export interface Preferences {
  full_name: string; email: string; level: "undergraduate" | "masters" | "phd";
  fields: string[]; countries: string[]; funding: "full" | "partial";
  start_year: number; nationality: string; gpa: number; gpa_scale: number; sensitive_consent: boolean;
}
export interface IntakeRequest {
  cv_text?: string; cv_pdf_base64?: string; transcript_text?: string;
  preferences: Preferences; vault_sections: Record<string, string>; vault_text?: string;
}
export interface IntakeResponse { facts: Fact[]; counts: { cv: number; transcript: number; vault: number }; warnings: string[]; }

export interface HardRuleResults { country: boolean; level: boolean; gpa: boolean; field: boolean; deadline: boolean; nationality: boolean; }
export interface Match {
  application_id: string; listing_id: string; name: string; is_mock: boolean; country: string; level: string;
  deadline: string; channel: Channel; fit_score: number; fit_reason: string; status: AppStatus;
  hard_rule_results: HardRuleResults; failed_rules: string[];
}
export interface DossierFact { id: string; topic: string; text: string; source_url: string; snippet: string; retrieved_at: string; }
export interface Dossier { listing_id: string; facts: DossierFact[]; degraded: boolean; }
export interface Edge {
  id: string; profile_fact_ids: string[]; dossier_fact_ids: string[]; reason: string;
  use_in: "cv_bullet" | "essay_opening" | "essay_body" | "attachment"; strength: number; selected: boolean;
}
export interface Segment { text: string; source_ids: string[]; status: "supported" | "removed" | "flagged"; }
export interface TailoredOutput { cv_summary: Segment[]; cv_bullets: Segment[]; essay: Segment[]; mode: "full" | "notes_only"; outline: string[]; }
export interface Claim {
  id: string; text: string; segment_index: number; section: "cv_summary" | "cv_bullets" | "essay";
  source_ids: string[]; verdict: "supported" | "unsupported" | "partial"; reason: string;
  deterministic_pass: boolean; llm_pass: boolean; challenged: boolean; overturned: boolean;
}
export interface RemovedClaim { text: string; reason: string; }
export interface VerificationReport {
  rounds: number; claims: Claim[]; removed_claims: RemovedClaim[]; overturned_claims: RemovedClaim[];
  unsupported_before: number; unsupported_final: number;
}
export interface AppEvent {
  event_no: number; at: string; run_id: string; application_id: string | null; agent: string;
  type: string; message: string; data: Record<string, unknown>;
}
export interface RunMetrics {
  tokens_total: number; cost_usd: number; latency_seconds: number; claims_total: number;
  claims_unsupported: number; claims_removed: number; claims_overturned: number;
  personal_refs_total: number; personal_refs_sourced: number; llm_calls: number; llm_fallbacks: number;
  retries: number; recovery_decisions: number; crustdata_credits: number;
}
export interface Run {
  run_id: string; mode: "A" | "B" | "Z"; status: RunStatus; started_at: string; finished_at: string | null;
  application_ids: string[]; metrics: RunMetrics | null; trace_url: string | null;
}
export interface ApplicationSummary {
  id: string; listing_id: string; name: string; is_mock: boolean; status: AppStatus; channel: Channel;
  fit_score: number | null; deadline: string; updated_at: string;
}
export interface Handoff { reason: string; portal_url: string; instructions: string; }
export interface Application {
  id: string; run_id: string;
  listing: { id: string; name: string; is_mock: boolean; provider: string; country: string; deadline: string; channel: Channel; ai_policy: string; source_url: string; essay_prompt: string; essay_word_limit: number; };
  status: AppStatus; fit_score: number | null; fit_reason: string | null; failure_reason: string | null;
  dossier: Dossier | null; edges: Edge[]; tailored: TailoredOutput | null; verification: VerificationReport | null;
  package: { cv_pdf_url: string; essay_url: string; checklist_url: string } | null;
  handoff: Handoff | null;
  submission: { confirmed: boolean; confirmation_code: string | null; channel: string; at: string | null };
  notifications: { at: string; text: string; sent: boolean }[];
  timeline: AppEvent[]; trace_url: string | null; metrics: RunMetrics | null;
}
export interface Gap { id: string; application_id: string; criterion: string; question: string; answered: boolean; }
```

`api.ts` spec: one generic `request(path, options)` that prefixes `NEXT_PUBLIC_API_BASE`, sets the JSON content type, throws an `ApiError` (with `status`, `code`, `message`) on non 2xx using the contract error body. When `NEXT_PUBLIC_USE_MOCKS` is `true` every exported function returns the matching mock JSON (imported statically) after a delay of 300 milliseconds. Exported functions (exact names):
`getHealth()`, `loadDemo()`, `intake(req)`, `getFacts()`, `patchFact(id, text)`, `addFact(category, text)`, `startRun(mode, topN, liveResearch)`, `getLatestRun()`, `getRun(id)`, `getRunEvents(id, after)`, `resumeRun(id)`, `getMatches(runId?)`, `getApplications(runId?)`, `getApplication(id)`, `handoffDone(id)`, `getGaps(runId?)`, `answerGap(id, text)`, `getFlags()`, `setFlags(flags, counts?)`, plus `fileUrl(appId, kind)` which returns the full URL for downloads.

`format.ts` helpers: `parseDate(s)`, `daysLeft(deadline)` (whole days from today, can be 0 or negative, returned as number), `timeAgo(s)`, `formatTime(s)`, `pct(n)`.

Mocks (`frontend/mocks/`, file names with underscores): `health.json`, `facts.json`, `intake.json`, `run_latest.json` (completed run with metrics), `run_running.json`, `events_page1.json` and `events_page2.json`, `matches.json` (5 matches: 3 mock with DEMO badge, 2 real, one skipped with failed_rules), `applications.json`, `application_awaiting.json` (status awaiting_user with handoff), `application_verified.json` (full tailored output with source ids, edges, a removed claim, an overturned claim, dossier facts), `application_submitted.json`, `application_failed.json`, `application_early.json` (status matched, nulls and empty lists), `gaps.json`. Content must match the types exactly (use the persona facts from `11_DEMO_PORTAL_AND_SYNTHETIC_DATA.md`).

Tests: type check passes (`npm run build` or the TypeScript check). A tiny script or test that imports every mock and checks it against the types is optional.
Acceptance: [ ] build passes. [ ] `api.getMatches()` in mock mode returns 5 matches.
Commit: `feat(frontend): types, api client and mocks [F01]`.

## F02. [x] Layout and shared components

Goal: app shell and every shared component from `15_DESIGN_BRIEF.md` section 10, with a temporary styleguide route.
Depends: F01. Time box: 90 min.
Create:
1. `frontend/app/layout.tsx` (font, background color, top bar), `frontend/components/TopBar.tsx` (product name, tabs Profile and Matches, Run status chip, connection indicator).
2. `frontend/lib/hooks.ts` with `usePolling(fn, intervalMs, shouldStop)`: calls `fn` immediately, then every `intervalMs`, stops when `shouldStop(lastResult)` is true or on unmount, exposes `{ data, error, loading, refresh }`. Never overlaps calls (skip a tick if the previous call is still pending).
3. `frontend/lib/status.ts` with `statusMeta(status)` returning `{ label, tone }` using the exact labels and tones in `15_DESIGN_BRIEF.md` section 7, `channelLabel(channel)`, `isFinalStatus(status)`, `isFinalRun(status)`.
4. Components in `frontend/components/`: `StatusBadge`, `ChannelBadge`, `DemoBadge`, `FitScore`, `SourcePill` (with popover), `SegmentText`, `EdgeCard`, `ClaimRow`, `DossierFactRow`, `TimelineItem`, `FileCard`, `StageTracker`, `StatTile`, `EmptyState`, `ErrorBanner` (with retry), `Skeleton`, `Toast`.
5. `frontend/app/styleguide/page.tsx` that renders every component with sample props from the mocks (delete in F09).
Requirements:
1. `SourcePill` takes `id`, and looks up the text: ids starting with C, T or P come from a `facts` prop map, ids starting with D come from a `dossier` prop. The popover shows the text, and for D ids the source URL and retrieved date. Keyboard accessible (Enter opens, Escape closes).
2. `TimelineItem` gives `recovery_decision` events a distinct card showing `data.trigger`, `data.chosen` and `data.reason`.
3. Never render raw null or undefined.
4. Tailwind utility classes only.
Acceptance: [x] `/styleguide` shows every component and state (loading, empty, error, each status). [x] type check passes.
Commit: `feat(frontend): layout and shared components [F02]`.

## F03. [x] Screen 1: Upload and Profile (`/`)

Goal: collect documents, preferences and the Vault, call intake, show editable facts, start a run.
Depends: F02. Time box: 90 min.
Read: `15_DESIGN_BRIEF.md` Screen 1.
Create: `frontend/app/page.tsx` and any section components under `frontend/components/profile/`.
Requirements:
1. Documents card: CV file input accepting PDF (convert to base64 with `FileReader.readAsDataURL`, strip the data URL prefix, send as `cv_pdf_base64`), or a text area (`cv_text`). Transcript text area.
2. Preferences card: full name, email, level, fields (tag input), countries (chips), funding, start year, nationality, GPA and GPA scale (numbers), all mapped into `Preferences`.
3. Vault card: 10 collapsible sections with the keys `sports`, `volunteering`, `certifications`, `leadership`, `awards`, `projects`, `languages`, `hardships`, `career_goals`, `why_abroad`, a progress meter, a tab for free text (`vault_text`), and the consent checkbox with the exact helper copy from the design brief.
4. A Load demo persona button (visible only when health says `demo_mode` is true) that calls `loadDemo()`, then `getFacts()` and fills the form from the preferences returned by `GET /api/profile/facts` (the response includes `preferences`).
5. Submit calls `intake(req)`. Show the loading state, errors via `ErrorBanner`, warnings from the response.
6. Parsed facts card: grouped by source, id pill, category, text. Inline edit saves on blur with `patchFact`. Sensitive facts show a lock icon and tooltip. Counts at the top.
7. Sticky bottom bar with `Run agent` (disabled until facts exist). It calls `startRun("B", 2, false)` by default, with a small Advanced control (visible in demo mode) that lets you choose mode A, B, Z and top_n 2 to 5. On success route to `/matches`. On 409 show "A run is already in progress" with a link to `/matches`.
Acceptance (mock mode and then real after F05): [x] Load demo persona fills everything. [x] Facts list shows grouped facts. [x] Run agent navigates to Matches.
Commit: `feat(frontend): upload and profile screen [F03]`.

## F04. [x] Screen 2: Matches (`/matches`)

Goal: ranked matches and the live agent feed.
Depends: F02. Time box: 90 min.
Read: `15_DESIGN_BRIEF.md` Screen 2 and section 13b.
Create: `frontend/app/matches/page.tsx` plus `frontend/components/matches/`.
Requirements:
1. On mount: `getLatestRun()`. If 404 show the empty state with a link to `/`.
2. Poll the run and its events every 2 seconds until `isFinalRun(status)`. Events use `after` equal to the last event number, appending new ones. Matches and applications refresh on each poll while running, then once more when the run finishes.
3. Left column: match cards (name, DEMO badge when `is_mock`, status badge, provider and country, FitScore, fit reason, eligibility chips from `hard_rule_results`, deadline with days left and warning tone under 14 days, channel badge, View application button enabled from status `researched` onward). Skipped matches in a collapsed section "Not eligible" with failed rules.
4. Right column: Agent activity feed (newest first, agent icon and name, time, message, distinct style for retry, fallback and recovery decision events). Auto scroll only when the user has not scrolled up.
5. Top: StageTracker for the run (Match, Research, Evidence, Write, Verify, Apply) derived from the statuses of applications, plus a Run metrics strip (StatTile for tokens, cost, time, claims checked, removed, overturned, recovery decisions) shown when `metrics` is not null, and a View trace button when `trace_url` is not null.
6. Gaps card at the bottom from `getGaps()` with a text field and Save (`answerGap`).
7. Interrupted run banner with a Resume button (`resumeRun`).
Acceptance: [x] mock mode shows the full layout. [x] polling stops when the run is final (verify with a console log in development, remove it).
Commit: `feat(frontend): matches screen with live feed [F04]`.

Checkpoint (Saturday 1:00 PM): F03 and F04 work on mocks and the backend B07 and B08 endpoints are ready for F05.

## F05. [x] Switch to the real backend

Goal: use the real API and fix contract mismatches.
Depends: F03, F04 and backend B08 or later. Time box: 45 min.
Do:
1. Set `NEXT_PUBLIC_USE_MOCKS=false`.
2. Run `/verify_contract` (see `12_ANTIGRAVITY_RULES.md`). Fix mismatches in `types.ts` or tell Memeshi in chat which side should change. Contract changes are a `contract:` commit.
3. Run the real flow: Load demo persona, Run agent, Matches.
4. Fix null handling and loading states found with real data.
Acceptance: [x] real matches appear for the persona. [x] no console errors.
Commit: `fix(frontend): connect to real backend [F05]`.

## F06. [x] Screen 3: Application Status (`/applications/[id]`)

Goal: the most important screen (proof of verification).
Depends: F05 and backend B13. Time box: 120 min.
Read: `15_DESIGN_BRIEF.md` Screen 3.
Create: `frontend/app/applications/[id]/page.tsx` plus `frontend/components/application/`.
Requirements:
1. Poll `getApplication(id)` every 2 seconds (4 seconds while `awaiting_user`) until `isFinalStatus`.
2. Header: back link, name, DEMO badge, StatusBadge, deadline countdown, ChannelBadge, StageTracker, View trace button when `trace_url`, banners for `awaiting_user` (button to `/handoff/[id]`) and `failed` (shows `failure_reason`), a submitted card with the confirmation code.
3. Left column tabs CV, Essay, Package. CV tab: summary and bullets as `SegmentText` with source pills; `flagged` segments with a warning underline; `removed` segments hidden behind a toggle "Show removed claims" (struck through with the reason from `verification.removed_claims`). Essay tab: same, plus a word counter against `listing.essay_word_limit`. Package tab: FileCards from `package` using `fileUrl`, plus the official link from `listing.source_url`. For `tailored.mode` equal to `notes_only` show the outline list instead of essay text with a clear label "Notes, not essay text".
4. Right column: Evidence used (selected edges only, read only, with the note), Research (dossier facts with links and dates, a warning when `degraded`), Verification report (tiles: claims checked, supported, removed, overturned, unsupported in final; list of claims with verdict icons and source pills; an Overturned by self challenge list; the green All claims verified banner only when `unsupported_final` is 0 and the report exists), Notifications sent (collapsible), Timeline (all events with recovery decision cards).
5. Early stages (nulls) show skeletons with labels, never crash.
6. Pass a `facts` map (from `getFacts()`) and the dossier to the SourcePill popovers.
Acceptance: [x] all 6 mock application variants render. [x] with real data a verified application shows the green banner and source pills.
Commit: `feat(frontend): application status screen [F06]`.

## F07. [x] Demo portal templates

Goal: styled portal pages (Memeshi provided working minimal templates in B20).
Depends: B20. Time box: 60 min. You edit only `backend/app/portal/templates/`.
Required HTML contract (do not change ids, names or text marked exact):
1. Every page header contains the exact text `DEMO PORTAL`.
2. `about.html`: heading with the school name, then each of the six information sentences as its OWN paragraph element, in the order given by the context variables (the Researcher reads this text). An optional extra paragraph is rendered when the context variable `injection` is set.
3. `apply.html` and `draft.html`: form fields named `full_name`, `email`, `summary`, `essay`; a Submit button with id `submit_button`; when the context variable `challenge` is true include `<div id="captcha_challenge">` containing the exact text `What is 7 plus 5?` and an input named `captcha_answer`. No iframes, no CAPTCHA provider markup.
4. `draft.html` includes a script that posts `{"draft_id": ..., "captcha_answer": ...}` to `/portal/api/submit` and shows: success block with the confirmation code in large text and the line `This is a demo portal`, an inline message `Please solve the challenge.` on 403, and `Something went wrong. Try again.` on 500.
5. `confirmation.html` and `error.html` as in `11_DEMO_PORTAL_AND_SYNTHETIC_DATA.md` section 5.2.
Style: simple, clearly a generic university site (not our app styling). Mobile friendly.
Acceptance: [x] all five pages render. [x] the CAPTCHA submit flow works by hand. [x] backend tests in `tests/test_portal.py` still pass.
Commit: `feat(portal): styled portal templates [F07]`.

## F08. [x] Screen 4: Handoff (`/handoff/[id]`)

Goal: the 3 step CAPTCHA handoff, mobile first.
Depends: F06 and backend B21. Time box: 60 min.
Read: `15_DESIGN_BRIEF.md` Screen 4.
Create: `frontend/app/handoff/[id]/page.tsx`.
Requirements:
1. Poll `getApplication(id)` every 4 seconds while waiting. States: waiting (default), checking (after pressing Done), success (confirmation code and link to the Status screen), check failed (friendly retry), not needed (status is not `awaiting_user`).
2. The three steps with large tap targets: Open the portal page (opens `handoff.portal_url` in a new tab), Solve the CAPTCHA and press Submit on that page, Come back and tap Done.
3. Done calls `handoffDone(id)` then polls until the status is `submitted` (success), or stays `awaiting_user` after 10 seconds (check failed).
4. Package summary with FileCards and the line "Checked: {unsupported_final} unsupported claims".
5. Layout max width about 560, works at 375 pixel width.
Acceptance: [x] mock `application_awaiting.json` shows the waiting state. [x] with the backend: full CAPTCHA flow ends in the success state. [x] looks right on a phone width in browser dev tools.
Commit: `feat(frontend): handoff screen [F08]`.

## F09. [x] Polish (Sunday evening)

Do: all loading, empty and error states on every screen; remove the styleguide route and any debug text; check readability at 1080p with browser zoom 110 percent; check that animations are under 300 milliseconds and nothing jumps while data loads; run the demo path three times (`15_DESIGN_BRIEF.md` section 12); add the Traced with neatlogs badge and View trace button where `trace_url` exists; take screenshots of each screen into `docs/evidence/screenshots/` for the posts.
Acceptance: [x] three clean runs of the demo path. [x] type check and lint pass.
Commit: `chore(frontend): demo polish [F09]`.

## F10. [x] Final fixes (Monday morning)

Only bug fixes from the final clean run (backend B25). Seed state: the demo should start at `/` with the Load demo persona button. Commit: `fix(frontend): final demo fixes [F10]`.

## Questions for Memeshi early

1. Which fields of `GET /api/applications/{id}` are filled at each stage (so you know what to skeleton)?
2. When will `trace_url` be filled and what does it contain (full trace link or the dashboard link)?
3. What is the exact `FRONTEND_BASE_URL` Telegram uses for the handoff link?
