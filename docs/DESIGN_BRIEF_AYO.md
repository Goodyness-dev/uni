# DESIGN_BRIEF_AYO.md

Design and frontend brief for Ayo. It explains the product, the design workflow, every screen, every component and every state, so you can design and build in parallel with Memeshi's backend.

Read these files together with this one: `PROJECT.md` (what we build), `ARCHITECTURE.md` section 9 (the API contract, your source of truth for data), `AGENTS.md` section 4 (frontend rules), `TASKS.md` (your tasks F01 to F10).

## 1. The product in 60 seconds

ScholarPilot is an agent that applies for scholarships for the user.

1. The user uploads a CV and transcript, fills a short preferences form, and writes or pastes a personal file called the Profile Vault (sports, volunteering, certifications, leadership, awards, hardships, goals).
2. The user presses Run agent.
3. The agent finds scholarships the user qualifies for, researches each school and programme, picks the user's strongest real evidence automatically, writes a tailored CV and essay, and checks every claim so nothing is invented.
4. The agent then submits where it can, or prepares a ready package. When a CAPTCHA blocks it, it stops and asks the user for ten seconds of help, then continues.
5. The user gets a Telegram message at each step.

Your job: make the product feel trustworthy, calm and clear, and make the demo look great on a screen recording.

## 2. What the UI must achieve (and what judges will see)

1. **Show the agent working.** A live timeline of events (research, edges chosen, claims verified, submitted) makes the agent feel real. Judges score the agent itself, so the UI must make its steps visible.
2. **Show trust.** Every generated sentence displays where it came from (source pills). Removed claims are visible. This is our main selling point: the agent never invents anything.
3. **Show the human handoff.** The CAPTCHA moment must be obvious, friendly and quick.
4. **Be demo proof.** Large readable text on a 1080p recording, no blank pages, no flicker, and clear loading and error states.
5. **Stay small.** Only 4 screens plus the demo portal pages. Do not add extra pages.

## 3. Design workflow (follow this order)

Total design time target: about 2 hours, spread over the first day. Code first beats pixels, so design directly in the browser as soon as the basics are set.

### Step 1: Setup (10 minutes)
1. Create the Next.js app in `frontend/` (TypeScript, Tailwind, app router).
2. Copy the API shapes from `ARCHITECTURE.md` section 9 into `frontend/lib/types.ts`.
3. Create `frontend/mocks/` with one JSON file per endpoint, matching the contract exactly. Set `USE_MOCKS=true`.
4. Create `frontend/lib/api.ts` so every screen calls it, never `fetch` directly.

### Step 2: Rough sketches (20 minutes)
1. Sketch each of the 4 screens on paper or in a free whiteboard. Boxes and labels only, no colors.
2. Share the 4 photos or screenshots with Memeshi in chat. Agree the data on each screen. This is the contract check.

### Step 3: Tokens and base components (30 minutes)
1. Set the design tokens (section 5): colors, type, spacing, radius.
2. Build the shared components (section 10) with mock data: StatusBadge, ChannelBadge, DemoBadge, FitScore, SourcePill, EdgeCard, ClaimRow, TimelineItem, FileCard, EmptyState, ErrorBanner, Skeleton.
3. Make a temporary `/styleguide` page showing every component and state. Delete it before submission, or hide it.

### Step 4: Build screens in this order (matches `TASKS.md`)
1. F03 Screen 1: Upload and Profile.
2. F04 Screen 2: Matches (with Run agent and the live event strip).
3. F06 Screen 3: Application Status (the most important screen).
4. F08 Screen 4: Handoff.
5. F07 Demo portal templates (plain pages, see section 9).

### Step 5: Review with Memeshi (every 90 minutes)
1. Run `/verify_contract` in Antigravity to check types against the real API.
2. Flip `USE_MOCKS` off as soon as the backend endpoint exists (F05).
3. Fix mismatches in the contract with a commit prefixed `contract:` and tell Memeshi.

### Step 6: Polish for the demo (Sunday evening, F09)
1. Run the full demo path (section 12) three times.
2. Check loading, empty and error states on every screen.
3. Check text is readable at 1080p with browser zoom at 110 percent.
4. Remove debug text and the styleguide page.

## 4. Design principles

1. **Calm and trustworthy.** This is about someone's future. Use clean layouts, generous whitespace, and a restrained palette. No flashy gradients.
2. **Plain language.** Write like a helpful person. Say "Verified" and "Removed because no source supported it", not technical jargon.
3. **Evidence first.** Wherever the agent writes something, show its source next to it.
4. **One clear action per screen.** Each screen has a single primary button.
5. **Show progress, never a spinner alone.** Use the event timeline and progress text.
6. **Honest labels.** Mock scholarships carry a DEMO LISTING badge. AI generated content is labeled as such.
7. **Mobile friendly, desktop first.** The demo runs on desktop, but layouts must not break on a phone width (the user may open the Handoff link from Telegram on a phone). Handoff screen MUST work well on mobile.

## 5. Design tokens (suggested, adjust if you prefer)

Colors (hex):
1. Background: `#F7F8FA`. Surface (cards): `#FFFFFF`. Border: `#E3E6EB`.
2. Text primary: `#14171F`. Text secondary: `#5B6475`.
3. Brand (primary actions, links): `#2457F5`. Brand light (tints): `#E8EEFF`.
4. Success: `#12805C` on `#E3F6EE`. Warning: `#B25E09` on `#FDF0DC`. Danger: `#C0392B` on `#FCE9E7`. Info: `#2457F5` on `#E8EEFF`. Neutral: `#5B6475` on `#EEF0F4`.
5. Source pill colors: CV facts (C) blue tint, Transcript (T) purple tint, Vault (P) green tint, Dossier (D) orange tint.

Typography: one sans serif family, for example Inter or the system font. Sizes: 14 for body in dense areas, 16 default body, 20 section titles, 28 page titles. Line height about 1.5. Use semi bold for headings, never all caps for long text.

Spacing: multiples of 4. Card padding 16 or 24. Gap between sections 24 or 32.

Radius: 12 for cards, 8 for inputs and buttons, full round for pills and badges.

Shadows: very soft or none. Use borders to separate.

Icons: one icon set (for example Lucide). Keep icons small and consistent.

## 6. Global layout

1. **Top bar** (all screens): product name on the left. Navigation tabs in the middle: Profile, Matches. Application and Handoff screens are reached from Matches or from Telegram links, so they do not need tabs. On the right: a Run status chip (Idle, Running with a small animated dot, Completed, Failed) and a small connection indicator (Live when polling works).
2. **Content width:** centered, max width about 1100, with a two column layout where needed.
3. **Footer note** on Screen 1 only: a privacy line (see copy in section 11).
4. **Toasts** for short messages (saved, error). They disappear after 4 seconds.

## 7. Status and channel maps (use these exactly)

The backend sends these status strings. Show the label and color shown here.

1. `found`: "Found", neutral.
2. `matched`: "Matched", info.
3. `skipped`: "Not eligible", neutral, with the reason on hover or below.
4. `researched`: "Researched", info.
5. `edges_selected`: "Evidence chosen", info.
6. `tailored`: "Written", info.
7. `verified`: "Verified", success.
8. `ready`: "Ready", success.
9. `submitting`: "Submitting", info with an animated dot.
10. `awaiting_user`: "Needs you", warning, with a pulsing dot. This is the attention state.
11. `submitted`: "Submitted", success with a check icon.
12. `prepared`: "Package ready", success outline (not a solid green, because it is not submitted).
13. `failed`: "Failed", danger, with the short reason.

Channels (badge on cards):
1. `email`: "Email application".
2. `portal_form`: "Online form".
3. `portal_captcha`: "Online form with CAPTCHA".
4. `package_only`: "Prepare only".

Also a small grey "DEMO LISTING" badge when `is_mock` is true.

## 8. Screens

### Screen 1: Upload and Profile (route: `/`)

**Purpose:** collect everything the agent needs and start a run. This is the first screen in the demo.

**API:** `POST /api/profile/intake`, `GET /api/profile/facts`, `PATCH /api/profile/facts/{id}`, `POST /api/runs`.

**Layout:** a single page with 4 stacked cards and a sticky action bar at the bottom.

**Card 1, Documents**
1. CV: file drop zone (PDF) plus a "paste text instead" toggle with a text area.
2. Transcript: text area (and optional file drop).
3. After upload show a green check and the file name. Show a size limit message if too large.

**Card 2, What are you looking for**
1. Level: segmented control (Undergraduate, Master's, PhD).
2. Fields of study: tag input (type and press Enter).
3. Countries of interest: multi select chips.
4. Funding needed: Full or Partial.
5. Start year: dropdown.

**Card 3, Your personal file (Profile Vault)**
1. Intro text: "The more real detail you give, the better the agent can find your strongest evidence. Everything here stays in your account."
2. Guided sections as collapsible panels, each with a text area and a small example hint: Sports and teams, Volunteering (role, hours, impact), Certifications, Leadership, Awards, Projects, Languages, Hardships you have overcome, Career goals, Why you want to study abroad.
3. A progress meter: "7 of 10 sections filled". It encourages detail but does not block.
4. A tab "Paste free text instead" with one big text area.
5. A consent checkbox: "Only use sensitive details (such as health, religion, family income) if a scholarship explicitly asks for them." Default unchecked. Add a short helper line explaining it.

**Card 4, Parsed facts (appears after intake)**
1. A list of numbered facts grouped by source: CV, Transcript, Vault. Each row shows the id pill (C1, T2, P7), the category, and the text.
2. Each row is editable inline (click to edit, save on blur, calls PATCH) and shows a small lock icon on facts marked sensitive with the tooltip "Not used unless a scholarship requires it and you agreed."
3. Counts at the top: "22 from CV, 9 from transcript, 31 from your personal file."

**Sticky action bar**
1. Left: summary text such as "62 facts ready".
2. Right: primary button "Run agent". Disabled until intake finished. On click: call `POST /api/runs` then go to Screen 2.
3. A small secondary toggle "Research mode": Cached or Live (default Cached). Optional, can be hidden for the demo.

**States**
1. Empty: no facts yet, show helper illustration and text.
2. Loading intake: progress bar and "Reading your documents".
3. Error: banner with a retry button ("We could not read that file. Try pasting the text.").
4. Success: facts list appears with a subtle highlight.

**Demo note:** for the video, the synthetic persona should preload with one click ("Load demo persona" button, visible only in demo mode).


### Screen 2: Matches (route: `/matches`)

**Purpose:** show scholarships found, how well they fit, and the live progress of the run.

**API:** `GET /api/matches?run_id=...`, `GET /api/runs/{id}`, `GET /api/runs/{id}/events?after=N` (poll every 2 seconds while running), `GET /api/gaps`.

**Layout:** two columns on desktop. Left (about 65 percent): match cards. Right (about 35 percent): a live event feed.

**Match card (one per scholarship)**
1. Title row: scholarship name, DEMO LISTING badge when mock, status badge.
2. Subtitle: provider, country, level, funding.
3. Fit score: a ring or bar from 0 to 100 with the number, color scaled (high success, mid warning, low neutral).
4. Fit reason: one sentence.
5. Eligibility checks: small chips with check or cross for country, level, GPA, field, deadline, nationality (from `hard_rule_results`).
6. Deadline: date plus "52 days left", turns warning color under 14 days.
7. Channel badge.
8. Footer: the button "View application" (goes to Screen 3) enabled once the application has progressed past `matched`.
9. Skipped (not eligible) cards are grayed out and collapsed under a "Not eligible (2)" section, with the failed rule shown.

**Live event feed (right column)**
1. Title: "Agent activity" with a live dot when running.
2. List of events newest first: time, agent icon and name, one sentence message. Examples: "Researcher found 6 sourced facts about the programme", "Edge Finder chose 3 pieces of evidence", "Verifier removed 1 unsupported claim".
3. Failure related events get a distinct style (warning for retries, info for fallbacks): "Model busy, switched to backup model".
4. Auto scroll is off when the user scrolls up.

**Top strip**
1. A progress stepper for the run: Match, Research, Evidence, Write, Verify, Apply. The current step highlights.
2. When the run completes show a summary: "3 submitted or ready, 1 needs you, 1 failed" and optional metrics (tokens, cost, time). The metrics strip is a stretch item but great for the demo (see section 13).

**Gap questions (optional)**
1. If `GET /api/gaps` returns items, show a soft card at the bottom: "Optional: help the agent find more evidence", with the question and a text field plus a Save button (calls `POST /api/gaps/{id}/answer`). It never blocks anything.

**States**
1. Waiting for first match: skeleton cards and "Looking for scholarships".
2. Empty: "No scholarships match yet. Try widening countries or fields."
3. Error: banner with retry.
4. Interrupted run: banner "Run was interrupted" with a Resume button (calls `POST /api/runs/{id}/resume`).


### Screen 3: Application Status (route: `/applications/[id]`)

**Purpose:** the most important screen. It proves the agent worked and that nothing was invented. Spend your best design time here.

**API:** `GET /api/applications/{id}` (poll every 2 seconds until the status is final).

**Layout:** header on top, then a two column body. Left column (about 60 percent): the documents. Right column (about 40 percent): evidence, verification and timeline. Collapse to a single column on mobile.

**Header**
1. Back link to Matches.
2. Scholarship name, DEMO LISTING badge, status badge, deadline countdown, channel badge.
3. A horizontal stage tracker with the same steps as Screen 2, showing which stage the application is in.
4. When the status is `awaiting_user`, a high contrast banner: "This application needs you" with the button "Open handoff" (goes to Screen 4).
5. When `failed`, a danger banner with `failure_reason`.

**Left column: Documents**
Tabs: CV, Essay, Package.
1. CV tab: the tailored CV summary and selected bullets. Each sentence renders as a line of text followed by small source pills (for example P7, C3). Status styling: `supported` normal, `flagged` with a warning underline, `removed` hidden by default with a toggle "Show removed claims" that reveals them struck through with the reason.
2. Essay tab: the essay with the same sentence by sentence source pills. A word counter against the limit.
3. Package tab: file cards for CV PDF, essay file and checklist, each with a Download button (links from `package`). Also the portal link when relevant.
4. Clicking a source pill opens a popover or side panel with: the original fact text (for C, T, P ids) or the dossier snippet plus source URL and retrieved date (for D ids).

**Right column: three stacked sections**
1. **Evidence used** (the edges, read only)
   1. Heading: "Your strongest evidence for this scholarship".
   2. One EdgeCard per selected edge: strength indicator, the reason sentence, the user fact pill (P7) and the programme fact pill (D3), and a "Used in" chip (CV bullet, essay opening, essay body, attachment).
   3. No approve or edit controls. This is information only. Add a note: "Chosen automatically by the agent and checked by the Verifier."
2. **Research** (the dossier)
   1. List of DossierFacts: topic chip, the fact, a link to the source, and the retrieved date.
   2. If `degraded` is true, show a warning: "We could not reach the programme pages, so no school specific claims were made."
3. **Verification report**
   1. Summary tiles: Claims checked, Supported, Removed, Unsupported in final (target 0). Rounds used.
   2. A list of claims: claim text, verdict icon (supported check, partial warning, unsupported cross), source pills, reason. Removed claims are shown with the removal reason.
   3. A green "All claims verified" banner when unsupported final is 0. This banner is a demo highlight.
4. **Notifications sent** (small, collapsible): list of Telegram messages with time and a sent check.
5. **Timeline**: the event list for this application, with failure and recovery events visually distinct (for example "Portal error, retried 3 times, switched to email"). This is how the recovery evidence appears in the product.

**Submission block** (bottom of left column or in the header area)
1. `submitted`: show the confirmation code in a success card with the date and channel.
2. `prepared`: show "Package ready. Submit this one yourself" with the official link and the checklist.
3. `awaiting_user`: show the handoff banner.

**States**
1. Early stages: sections not yet available appear as skeletons with labels ("Research in progress").
2. Failed: danger banner plus the timeline.
3. Not found: friendly 404 with a link back.


### Screen 4: Handoff (route: `/handoff/[id]`)

**Purpose:** the quick human step when a CAPTCHA or login blocks the agent. It must be understandable in 5 seconds and work on a phone, because the user may arrive from a Telegram link.

**API:** `GET /api/applications/{id}` (read `handoff` and `package`), `POST /api/applications/{id}/handoff/done`.

**Layout:** a single centered column, max width about 560.

1. Title: "One quick step needed".
2. Explanation card in plain words: "The portal for {scholarship} is asking you to solve a CAPTCHA. For your safety and the portal's rules, only you can do that. Everything else is already filled in."
3. A three step numbered guide with big tap targets:
   1. "Open the portal page" (button, opens `portal_url` in a new tab).
   2. "Solve the CAPTCHA and press Submit on that page."
   3. "Come back and tap Done."
4. Summary of what is ready: small file cards for the CV and essay with a short "Checked: 0 unsupported claims" line.
5. Primary button: "Done, I submitted it". On click: call the done endpoint, show "Checking the confirmation" with a spinner, then the success state with the confirmation code, or an error state ("We could not see a confirmation yet. Make sure you pressed Submit on the portal.") with a retry button.
6. Secondary link: "Skip for now" (leaves the application as Needs you).

**States**
1. Waiting: the default view.
2. Checking: spinner and message.
3. Success: big check, confirmation code, link to the Status screen.
4. Failed check: friendly retry.
5. Not needed: if the application is not awaiting the user, show "Nothing needed right now" with a link to the Status screen.


## 9. Demo portal pages (not part of the product, simple and clearly fake)

Served by the backend under `/portal`. They are plain pages that look like a generic university scholarship site. Label every page "DEMO PORTAL" in the header so nobody mistakes it for a real site. Backend contract in `ARCHITECTURE.md` 9.8. Templates live in `backend/portal/templates/` (this is your folder).

1. **About page** (`/portal/about/{listing_id}`): a short fictional school page with a heading, a mission paragraph, a "Programme focus" section, a "What we value" list, and a "Programme director" box with a research interests line. The Researcher reads these as public sources, so the text must be clear and honest, and each fact should be in its own paragraph or list item.
2. **Apply form** (`/portal/apply/{listing_id}`): fields full name, email, summary (text area), essay (text area), a document upload box (can be cosmetic), and a submit button. When the CAPTCHA flag is on, include the fake challenge block with the element id `captcha_challenge` (a simple question such as "What is 7 plus 5?" and an answer input). Do not use any real CAPTCHA widget or provider markup.
3. **Draft page** (`/portal/draft/{draft_id}`): the same form but prefilled with the agent's values, and the challenge visible if the flag is on. The user solves it and presses Submit.
4. **Confirmation page**: a success message with the confirmation code in large text (for example DEMO1234), the date and a note "This is a demo portal".
5. **Error page** for the 500 simulation: a plain "Something went wrong" message. It must really return an error status from the backend, so the page is cosmetic.

## 10. Shared components (build these first)

1. **StatusBadge**: takes a status string and renders the label and color from section 7.
2. **ChannelBadge** and **DemoBadge**.
3. **FitScore**: ring or bar with number, color scaled.
4. **SourcePill**: small rounded pill with the id (C1, T2, P7, D3) tinted by source. Click opens a popover with the source content. Keyboard accessible.
5. **SegmentText**: renders a sentence plus its source pills, with `supported`, `flagged` and `removed` styles.
6. **EdgeCard**: strength meter, reason, two pill groups, "Used in" chip.
7. **ClaimRow**: verdict icon, claim text, source pills, reason.
8. **DossierFactRow**: topic chip, text, source link, retrieved date.
9. **TimelineItem**: time, agent icon, message, type styling (normal, retry, fallback, removed claim, blocker, confirmed).
10. **FileCard**: icon, file name, Download button.
11. **StageTracker**: horizontal steps with done, current and upcoming states.
12. **EmptyState**, **ErrorBanner** (with retry), **Skeleton**, **Toast**.
13. **StatTile**: number plus label, for the verification summary and run metrics.

## 11. Copy and tone

Voice: warm, clear, honest. Short sentences. No hype.

Fixed copy to use:
1. Privacy line on Screen 1: "Your documents and personal file are sent to an AI provider to be processed. They are not shared with scholarship providers unless you submit an application."
2. Sensitive details helper: "Details like health, religion or family income are never used unless a scholarship asks for them and you agreed above."
3. Verification banner: "All claims verified. Every sentence is backed by your CV, your personal file or a public source."
4. Removed claim label: "Removed because no source supported it."
5. Edges note: "Chosen automatically by the agent and checked by the Verifier."
6. Demo labels: "DEMO LISTING" and "DEMO PORTAL".
7. Handoff reason for CAPTCHA: "For safety and the portal's rules, only you can solve a CAPTCHA."

Do not use: "guaranteed", "AI powered magic", or any claim about winning a scholarship.

## 12. The demo path the screens must support (about 3 minutes total in the video)

The UI part of the video shows this exact flow, so these moments must look polished:

1. Screen 1 with the demo persona loaded: facts list visible (5 seconds).
2. Click Run agent, land on Screen 2. Cards appear one by one with fit scores while the event feed scrolls (about 30 seconds).
3. Open the top match on Screen 3. Point at: the dossier sources, the Evidence used cards, the source pills on the essay, and the green "All claims verified" banner with the removed claim shown (about 40 seconds).
4. The CAPTCHA application shows "Needs you". Open Screen 4, press the portal button, solve the fake challenge, press Done, and watch the success state with the confirmation code (about 25 seconds).
5. Telegram buzzing on the phone is filmed separately by Memeshi.

Make sure animations are short (under 300 milliseconds) and nothing jumps while data loads.

## 13. Stretch items (only if everything else is done)

1. **Run metrics strip** on Screen 2: tokens, cost, time, claims checked, claims removed, using `metrics` from `GET /api/runs/{id}`. Valuable for the demo.
2. **Run A versus run B comparison view**: a simple two column page with the metrics from both runs. Only if the backend exposes both.
3. **Dark mode.**
4. **Live research toggle** on Screen 1.

## 14. Things NOT to design or build

1. Login, signup or account pages.
2. Settings pages, billing pages or dashboards beyond the 4 screens.
3. Editing or approving the Evidence (it is automatic and read only).
4. Any page that shows real people's data. The persona is fictional.
5. A real CAPTCHA widget or anything that imitates a real provider's branding.
6. Anything that displays a sensitive fact in the generated output (the backend filters them, but never render a fact flagged `sensitive` in documents).

## 15. Technical rules recap (from `AGENTS.md`)

1. TypeScript strict. Types match the contract exactly.
2. All network calls go through `frontend/lib/api.ts`. Mock mode returns JSON from `frontend/mocks/`.
3. Poll every 2 seconds while a run or application is not final. Stop polling when final.
4. Show loading, empty and error states on every screen.
5. Dates arrive as `YYYY/MM/DD` and `YYYY/MM/DD HH:MM:SS` in UTC. Format them for display with a helper and show relative times such as "52 days left".
6. Commit small and often with the format `<type>(<area>): <what> [<task id>]`. Entire checkpoints depend on it. Use the Antigravity CLI for sessions you want captured.
7. Never edit backend folders. If you need a contract change, make a `contract:` commit and tell Memeshi.

## 16. Deliverables and definition of done for Ayo

1. [ ] Types and mocks for every endpoint (F01).
2. [ ] Layout, navigation and shared components (F02).
3. [ ] Screen 1 Upload and Profile (F03).
4. [ ] Screen 2 Matches with live feed (F04).
5. [ ] Real backend connected, contract mismatches fixed (F05).
6. [ ] Screen 3 Application Status with source pills, evidence, verification and timeline (F06).
7. [ ] Demo portal templates (F07).
8. [ ] Screen 4 Handoff, tested on a phone width (F08).
9. [ ] Polish pass, all states covered, styleguide page removed (F09).
10. [ ] Final bug fixes and demo seed state (F10).
11. [ ] Three clean runs of the demo path (section 12) without a visual glitch.
12. [ ] Screenshots of each screen saved in `docs/evidence/` for the build in public posts.

## 17. Questions to ask Memeshi early

1. Which fields on `GET /api/applications/{id}` are filled at each stage, so you know what to skeleton?
2. Is there a seed endpoint or script that loads the demo persona in one click?
3. How is the Telegram link to the Handoff screen formed (the base URL of the frontend)?
4. Will the backend serve the portal pages from your templates, or do you need to export static files?
