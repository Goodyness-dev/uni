# PRODUCTION_UPGRADE.md

How to move ScholarPilot from the hackathon demo to a real product: add Playwright browser automation, then support real scholarship sites safely, then harden everything for real users.

Start this file ONLY after the hackathon submission is posted and the demo version meets its definition of done in `PROJECT.md`. Do not start any of this during the 48 hours. Hackathon scope stays small.

This is a planning and engineering guide, not legal advice. Anything marked VERIFY needs checking with the official source or a qualified person before you rely on it.

## 1. Gate: when are we ready to start

All of these must be true:

1. [ ] The hackathon submission is posted and the evidence in `EVIDENCE.md` is saved.
2. [ ] The demo pipeline runs end to end on the synthetic persona with zero unsupported claims in mode B.
3. [ ] The test suite passes without network or API keys.
4. [ ] The repo has a tagged release such as `hackathon_final` so the submitted version is always recoverable.
5. [ ] You have decided who the first real users are (for example 10 to 20 students you know personally) and they agreed to test.

## 2. Principles that do not change in production

1. **Never invent applicant content.** The Verifier stays mandatory and cannot be turned off for real users. Mode A exists only for internal testing.
2. **Never bypass CAPTCHAs, bot protection or login walls.** No solver services, no stealth plugins, no fingerprint spoofing, no rotating proxies. If a site blocks automation, we hand off to the user.
3. **The user stays in control.** The default for real portals is that the agent fills the form and the USER presses the final submit button after reviewing. Full auto submit is allowed only where it is clearly permitted (see the autonomy levels in section 5).
4. **Respect site rules.** Read each portal's terms of use and robots rules before writing an adapter. If automation is forbidden, that portal stays at package only or assisted mode.
5. **Honest status.** `submitted` is set only after a confirmation is observed. Otherwise the status is `prepared`, `awaiting_user` or `unconfirmed`.
6. **Privacy first.** The Profile Vault is the most sensitive data we hold. Collect the minimum, encrypt it, let users delete it.
7. **Respect AI use rules.** Some scholarships restrict or require disclosure of AI assisted writing. Restricted listings get an info briefing and a draft pack with no generated essay (section 9).

## 3. Roadmap overview

1. **Phase 1, Playwright on the demo portal** (about 3 to 5 days): replace the plain HTTP submit with a real browser driver, keep the same blocker detection and handoff.
2. **Phase 2, assisted mode on real portals** (about 1 to 2 weeks): adapters for 2 to 3 real portals that prefill and stop before submit.
3. **Phase 3, live listings pipeline** (about 1 to 2 weeks): replace the local JSON file with a curated, reviewed, refreshable source.
4. **Phase 4, production platform** (about 2 to 3 weeks): accounts, database, queue, encryption, deployment, monitoring, billing.
5. **Phase 5, compliance and launch** (parallel, from Phase 2): data protection, terms, privacy policy, pilot with real users.

Do the phases in order. Each phase has its own definition of done.

## 4. Phase 1: add Playwright to the demo portal

Goal: the agent controls a real browser against OUR demo portal, which is a safe place to build and test browser automation.

### 4.1 Setup

1. Add the `playwright` package to `backend/requirements.txt`.
2. Install the browser binaries once with the Playwright install command for Chromium (`playwright install chromium`). This downloads a browser. No Docker needed locally.
3. Add new environment variables: `BROWSER_HEADLESS` (true for tests, false for handoff sessions), `BROWSER_PROFILE_DIR` (a local folder for persistent sessions, gitignored), `BROWSER_TIMEOUT_MS`, `SCREENSHOT_DIR`.
4. Add `backend/data/browser_profiles/` and `backend/data/screenshots/` to `.gitignore`.

### 4.2 New folder layout

```
backend/app/browser/
  driver.py          (start and stop browser, persistent context, screenshots)
  blockers.py        (DOM based blocker detection, replaces the string checks)
  fillers.py         (generic helpers: fill by label, select option, upload file, check box)
  confirm.py         (read a confirmation message or code from the page)
  adapters/
    base.py          (the PortalAdapter interface)
    demo_portal.py   (adapter for our demo portal)
```

### 4.3 The PortalAdapter interface

Every portal gets one adapter class with the same methods so the Applier does not care which portal it is:

1. `open(application)`: open the apply page and wait for it to load.
2. `detect_blockers()`: returns a list such as `captcha`, `login`, `otp`, `terms_wall`, `maintenance`, `rate_limited`. Empty means clear.
3. `map_fields(application)`: returns a list of `(field_label, value, source_ids)`. Values come only from verified tailored output and approved profile facts.
4. `fill()`: fill each field, upload documents (CV PDF, essay file), tick required boxes the USER consented to in advance.
5. `review_snapshot()`: take a full page screenshot and save the list of filled values for the audit log.
6. `submit()`: click the final submit. Only called when the autonomy level allows it.
7. `read_confirmation()`: return the confirmation code or message, or none.

### 4.4 Rules for the browser code

1. Prefer role and label based locators (find by label text, role, placeholder). Avoid brittle CSS paths and absolute positions.
2. Use explicit waits for the elements we need. No fixed sleeps except tiny ones.
3. Every browser action is a `tool` span in neatlogs with metadata: portal, step name, success, duration, screenshot path.
4. Take a screenshot at: page opened, after fill, blocker detected, after submit, confirmation. Store paths in the application record.
5. Blocker detection checks the live DOM: visible iframes from known challenge providers, challenge related text, password or one time code inputs, redirects to login paths. Any hit stops automation immediately. Nothing is retried against a blocker.
6. Never store portal passwords. If a login is needed, the user logs in themselves in a visible window (see 4.5).
7. Timeouts and retries follow `ARCHITECTURE.md` section 8 (3 attempts with backoff, then fallback).
8. The browser runs inside a context manager so it always closes, including on errors.

### 4.5 Handoff with a real browser session (resume that actually works)

The demo version hands off to a portal draft page. With Playwright, the handoff gets more real:

1. When a blocker is detected, the Applier saves progress (filled values, screenshot) and sets `awaiting_user`.
2. The backend opens a HEADED browser window (visible, not headless) using the persistent profile directory, on the page where the agent stopped. This works when the user runs the app locally on their machine.
3. The user solves the CAPTCHA or logs in inside that window. They do not need to tell us any credentials.
4. The user taps Done in the app or on Telegram. The agent reattaches to the same persistent context, checks that the blocker is gone, continues filling, and (if allowed) submits or stops before submit.
5. For a hosted version where the user is not on the same machine, do NOT stream a remote browser to the user as a first step. Use the simpler fallback: deliver a prefilled package and a step list, and have the user complete the portal on their own device. A remote browser handoff is a later project (section 12).

### 4.6 Tests for Phase 1

1. Unit tests for `blockers.py` against saved HTML fixtures (a page with a challenge, a page with a login form, a clean page).
2. Integration test: run the adapter against the demo portal in headless mode with the CAPTCHA flag off, expect a confirmation code.
3. Integration test: CAPTCHA flag on, expect `captcha` blocker and `awaiting_user`.
4. Integration test: portal 500 flag on, expect retries then fallback.
5. All browser tests marked so they can be skipped in the quick check (they are slower).

### 4.7 Phase 1 definition of done

1. [ ] The demo portal path uses Playwright, with the HTTP path kept as a fallback option behind a config flag.
2. [ ] Headed handoff and resume works on a local machine.
3. [ ] Screenshots are captured at each step and visible on the Application Status screen.
4. [ ] All four injected failures still produce the same recoveries.
5. [ ] neatlogs traces show every browser step as a span.

## 5. Phase 2: real scholarship portals (assisted first)

### 5.1 Autonomy levels per listing

Every listing gets an `autonomy_level` field, set by us after review, never by the agent:

1. **Level 0, package only**: the agent prepares tailored documents, a checklist and the portal link. The user does everything on the site. This is the default for any new portal.
2. **Level 1, assisted prefill**: the agent opens the portal, fills fields and uploads files, takes screenshots, then STOPS. The user reviews and presses submit themselves. This is the target for most real portals.
3. **Level 2, user confirmed submit**: the agent fills and shows the user a final review screen in our app (the filled values and screenshot). The user taps Approve, and the agent clicks submit. Allowed only where the portal terms permit automated form submission.
4. **Level 3, full auto**: no review step. Only for channels that are clearly intended for automated or bulk submission, such as an application email address or an official API. Never for portals whose terms forbid automation.

Rule: a listing can only move up a level through a written entry in `docs/portal_reviews/{listing_id}.md` stating what the terms say, who checked, and on what date.

### 5.2 Portal review checklist (do this before writing any adapter)

1. [ ] Read the portal terms of use. Do they forbid bots, scripts or automated tools? Record the exact section reference.
2. [ ] Check the robots file for rules about the application paths. Record it.
3. [ ] Does the site offer an official API, an email submission route or a partner programme? Prefer these over browser automation.
4. [ ] Is a login required? Is two factor or a one time code used? (If yes, the user must always be present for that step.)
5. [ ] Is a CAPTCHA or bot protection used? (If yes, handoff step is mandatory.)
6. [ ] Does the application contain declarations the USER must personally make (truthfulness statement, consent, signature)? Those boxes are always ticked by the user, never by the agent, unless the user pre consented in an explicit and logged way. Recommended default: the user ticks declarations themselves.
7. [ ] Does the scholarship restrict AI assisted writing? (see section 9)
8. [ ] If automation is not allowed or unclear: set Level 0 and email the provider to ask. Keep the reply in the review file.
9. [ ] Decide the level, record the decision, get a second person to sign off.

### 5.3 Building an adapter for a real portal

1. Pick 2 or 3 portals first, preferably ones with simple forms and clear terms. Do not start with the hardest portal.
2. Record the form once by hand and note every field, validation rule, file type and size limit. Playwright's code generation tool can help you explore, but never keep generated code as is. Rewrite it with label based locators.
3. Save sanitized HTML fixtures of each step (no personal data) in `backend/tests/fixtures/portals/{portal}/`.
4. Write the `PortalAdapter` methods against fixtures first, then test against the live portal using a throwaway test account and ONLY in assisted mode (stop before submit) during development.
5. Never run development tests that actually submit to a real scholarship. If a portal offers a sandbox or test mode, use that.
6. Add a field mapping table: portal field label to our data source (profile field, fact id, tailored essay). Fields with no source are left empty and listed for the user to fill, never guessed.
7. Handle word limits and character limits in code: if the essay exceeds the portal limit, send it back to the Tailor with the limit. Never silently truncate.
8. Add a `canary` test that loads each portal's start page weekly and checks the expected field labels still exist. A failed canary sets that listing to Level 0 automatically and notifies us.

### 5.4 User consent for each real submission

Before any Level 1, 2 or 3 action on a real portal, the app records a consent entry with: user id, listing id, date and time, the autonomy level, the exact list of documents and answers to be used, and a statement that the user confirms the information is true. Store it in the audit log. No consent entry means Level 0 only.

### 5.5 Phase 2 definition of done

1. [ ] Portal review files exist for every supported portal.
2. [ ] At least 2 real portals work at Level 1 with pilot users, with screenshots and no failed submissions.
3. [ ] Weekly canary checks run and alert on changes.
4. [ ] Consent and audit logging works.
5. [ ] A real handoff for a CAPTCHA worked with a pilot user on a real portal.

## 6. Phase 3: live scholarship listings (replace the local JSON)

The hackathon version uses a hand copied local file. Production needs fresh, accurate listings, but listing accuracy matters more than listing volume. A wrong deadline or wrong eligibility rule damages trust fast.

### 6.1 Sources, in order of preference

1. **Official provider pages and feeds** you are allowed to read (RSS, public APIs, structured data).
2. **Partnerships and manual curation**: a small editorial team or ambassadors who enter and review listings by hand through an admin screen.
3. **Licensed or partner datasets**, if available and affordable.
4. **Automated page reading** of official pages, only where the site allows it, at a low rate, with a clear user agent, and always followed by human review before the listing goes live.

Do not scrape sites that forbid it. Do not copy large amounts of text from other aggregators. Link to the official source and store a short factual summary.

### 6.2 Listing pipeline

1. **Collect**: fetch candidate pages or entries and store the raw text with the source URL and fetch time.
2. **Extract**: an LLM extracts the listing schema from `DATA_SPEC.md` section 3 from the raw text, returning a snippet for each field showing where it came from.
3. **Validate in code**: dates parse, deadlines are in the future, required fields present, snippets really appear in the raw text. Reject anything that fails.
4. **Human review queue**: a reviewer approves, edits or rejects each new or changed listing in an admin page. Nothing goes live without approval.
5. **Publish** with `reviewed_by`, `reviewed_on`, `source_url`, `last_verified_on`.
6. **Refresh**: recheck listings on a schedule (weekly, daily near deadlines). If the source page changed, put the listing back in the review queue and mark it "needs recheck" for users.
7. **Expire**: automatically hide listings after the deadline unless the provider states a rolling deadline.

### 6.3 Show uncertainty honestly

The UI shows "last verified" dates. If a listing has not been verified in 30 days, it shows a warning. Eligibility results display "likely eligible, please confirm on the official page" rather than a guarantee.

### 6.4 Phase 3 definition of done

1. [ ] The listings table in the database replaces `listings.json`.
2. [ ] An admin review page exists (basic, can be internal only).
3. [ ] At least 25 reviewed listings relevant to Nigerian and African applicants.
4. [ ] Refresh and expiry jobs run.
5. [ ] Zero listings live without a reviewer name and a verified date.

## 7. Live research hardening (Researcher)

1. Switch `LIVE_RESEARCH` on for production, but keep the cache. Dossiers expire after 14 days or when the listing changes.
2. Fetch only public institutional pages. Respect the robots file, use a low request rate, a clear user agent, and timeouts.
3. Keep the rule that every fact needs a source URL and a snippet that really appears in the page text (checked in code).
4. For professors, use only public faculty pages and publication listings. No personal social media, no private contact details, no speculation about people. Do not name drop a professor unless the research area genuinely matches a user fact.
5. If a page cannot be fetched, mark the dossier degraded and the Tailor makes no school specific claims.
6. Log the retrieval date. Show the "retrieved on" date next to dossier facts in the UI.

## 8. Phase 4: production platform

### 8.1 What changes from the demo

1. **Accounts and login**: add authentication (a managed provider is faster and safer than building it). Every row gets a `user_id`. Every query filters by it. Add tests that prove user A cannot read user B's data.
2. **Database**: move from SQLite to a managed Postgres database. Keep migrations in version control.
3. **Job queue**: replace the background thread with a proper job runner and a queue, so runs survive restarts and can scale. Keep idempotent steps and the existing retry logic.
4. **File storage**: store CVs, tailored packages and screenshots in encrypted object storage with short lived signed links. Never in the web server folder.
5. **Encryption**: encrypt the Profile Vault and uploaded documents at rest with per user data keys or at least application level encryption. Secrets come from a secrets manager, not env files in the repo.
6. **Deployment**: deploy the backend and frontend to managed hosts. Docker is now reasonable for the backend and for the browser worker. The browser automation worker runs as a separate service with limited network access and strict resource limits.
7. **Observability**: keep neatlogs for agent traces. Add error tracking, uptime monitoring and alerts for failed runs, canary failures and cost spikes.
8. **Cost controls**: per user daily limits on runs and LLM spend, a global budget alarm, and caching of dossiers and listing extractions.
9. **Rate limiting and abuse protection** on every public endpoint.
10. **Backups and restore tests** monthly.
11. **Telegram**: move from one chat id in the env to per user linking (the user starts the bot and we store their chat id after they opt in). Allow turning notifications off.

### 8.2 Remote browser handoff (later, optional)

If users need CAPTCHA help while not on our machine, options in order of safety:

1. Prefilled package plus instructions (already built).
2. A browser extension that fills the portal form on the user's own browser from our package, so the user's own session, IP and CAPTCHA are used. This is often the best production answer for assisted mode because it runs where the user is.
3. A remote streamed browser. Highest complexity and risk (security, session handling, site terms). Only consider after the first two work.

### 8.3 Phase 4 definition of done

1. [ ] Auth and per user isolation tested.
2. [ ] Postgres, queue, encrypted storage deployed.
3. [ ] Deletion works: a user can delete all their data and we can prove it.
4. [ ] Monitoring and alerts live.
5. [ ] Cost limits enforced.

## 9. AI use policies per scholarship

Many scholarships have rules about AI assisted writing, authenticity and who must write the essay. Add to each listing:

1. `ai_policy`: `allowed`, `disclose`, `restricted` or `unknown`, with a source snippet and the date it was checked.
2. `policy_checked_on` and `policy_source_url`.

### 9.1 What the agent does for each policy value

1. **allowed**: the full pipeline runs, including the tailored essay.
2. **disclose**: the full pipeline runs. The Telegram message and the Application Status screen remind the user to include the required AI disclosure, with suggested wording they can edit.
3. **restricted**: the agent switches to Info and Draft Pack mode (section 9.2). It does NOT write essay or statement sentences.
4. **unknown**: treated exactly like restricted until the user confirms the rules on the official page and taps "AI is allowed" in the app. The Telegram message tells them to check.

The user is always the author who submits. The product helps with research, evidence and drafting, and the user reviews and approves the content.

### 9.2 Info and Draft Pack mode (restricted or unknown)

The agent skips the Tailor essay step and instead sends the user a useful briefing on Telegram, with a draft pack attached in the app.

**Telegram briefing (one message plus one follow up with the files link), contents:**
1. Scholarship name, deadline and days left, funding, channel and the official link.
2. Eligibility result: which rules you pass, which are unclear.
3. What the committee and programme value, from the research dossier, each with its source link.
4. Your strongest evidence for this scholarship: the selected edges shown as short notes with fact ids, for example "P7: 200 hours teaching Python. Matches the programme focus on community impact."
5. Gaps: what the scholarship wants that your profile does not show yet.
6. The AI policy line: what the rule says and the source link.
7. A required documents checklist and the next steps in order.
8. The professor or programme lead notes, only if public and relevant, with source links.

**Draft pack (stored in the app, linked from Telegram), contents:**
1. **Tailored CV draft**: built only by selecting and reordering the user's own CV bullets and using their original wording. No new sentences. The Verifier still checks it.
2. **Prefilled factual form answers**: name, education, grades, dates, activities, awards, taken straight from verified facts.
3. **Essay outline, not essay text**: the prompt, the word limit, a suggested structure, and under each section the user's own facts to draw on (with fact ids) and the dossier points to connect to. Written as notes and questions, not as paragraphs the user could paste in.
4. **Checklist and deadlines.**
5. **Optional fact check of the user's own writing**: the user writes the essay themselves, pastes it into the app, and the Verifier checks every claim against their facts and flags anything unsupported. It does not rewrite their text.

**Rules for this mode:**
1. No generated essay or statement sentences, no "sample paragraph", no rephrasing the user's essay.
2. The Applier stays at autonomy level 0 or 1 for these listings. Any essay field is left for the user to fill.
3. The status is `prepared` with `ai_policy_mode` set to `info_pack`, so the UI shows why.
4. If the policy only requires disclosure, use the `disclose` behavior instead, which allows the full draft.

### 9.3 Telegram template for restricted listings

```
{name}: briefing ready. Deadline {deadline} ({days} days left).
Rule: AI written essays are not allowed, so I did not write yours. I prepared your CV draft, form answers, an essay outline with your own evidence, and a checklist.
Your strongest points: {edge_notes}
Open your pack: {frontend_url}/applications/{id}
Official page: {source_url}
```

Send the sourced details (what the programme values, gaps, next steps) as a second message so the first stays short.

### 9.4 Data and code changes

1. Add `ai_policy`, `policy_source_url`, `policy_checked_on` to the listing schema and the review checklist in section 5.2.
2. Add `tailor_mode` to the Tailor: `full` or `notes_only`. In `notes_only` the Tailor returns the CV selection and the outline structure only.
3. Add `info_pack` as an Applier outcome and a new application field `ai_policy_mode`.
4. Add a Telegram template for the briefing to `DATA_SPEC.md` section 8.
5. Add tests: a restricted listing must never produce essay prose, the CV draft must contain only original wording, and the user's own essay check must never modify their text.

## 10. Legal and compliance (start in Phase 2, finish before launch)

VERIFY all of these with the official texts or a qualified advisor.

1. **Data protection law**: Nigeria's data protection law (the Nigeria Data Protection Act 2023 and its regulator's guidance) applies to Nigerian users. If you serve users or programs in the UK or EU, GDPR style rules may apply too. Identify your lawful basis (consent), purposes, retention periods and rights handling (access, correction, deletion).
2. **Privacy policy and terms**: plain language, explaining that documents are processed by LLM providers, what is stored, for how long, and how to delete.
3. **LLM provider terms**: use paid API plans with data processing terms that say customer data is not used to train models. Do not rely on free tier terms for real user data.
4. **Sensitive data**: keep the sensitive facts filter. Collect sensitive data only when a listing needs it and the user opts in.
5. **Minors**: decide whether under 18 users are allowed. If not, add an age gate.
6. **Terms of third party portals**: tracked per listing in `docs/portal_reviews/`.
7. **Consent and audit records**: keep them for as long as the law and your policy require.
8. **Disclaimers**: we do not guarantee selection, and eligibility results are guidance.
9. **Payments**: use a payment provider that supports your users' currencies and cards, and state refund rules.
10. **Incident plan**: a short written plan for a data leak or a wrong submission (who is told, in what time, how users are notified).

## 11. Quality and safety gates in production

1. The Verifier is mandatory. Releases are blocked if the verification test suite fails (the persona traps from `DATA_SPEC.md` section 4 become permanent regression tests).
2. A fixed evaluation set of 10 synthetic persona and listing pairs runs before each release. Track unsupported claims, cost and latency per release in neatlogs. Do not ship a version where unsupported final claims are above zero.
3. Every real submission stores: the package, the screenshots, the consent entry, the verification report and the confirmation. Users can download all of it.
4. A kill switch per listing and a global kill switch for browser automation.
5. Human review of a sample of real applications during the pilot (with user permission).

## 12. Business steps alongside the build

1. Update `CFO_PLAN.md` with real measured costs, including browser worker hosting and review team time.
2. Run a pilot with 10 to 20 users, one scholarship season, with free or discounted access in return for feedback.
3. Measure: time saved per application, number of applications prepared and submitted, users who got interviews or awards, support requests, cost per application, and verification catches.
4. Decide pricing from real data, then test the Season pass and per application tiers.
5. Partnerships to explore: university career offices, scholarship coaches, and student groups. They also help with listing curation.

## 13. Task list for this upgrade

Use the same format as `TASKS.md`. Owners are placeholders.

### Phase 1
1. P01. [ ] Add Playwright dependency, install Chromium, env variables, gitignore entries.
2. P02. [ ] `browser/driver.py` with persistent context and screenshots.
3. P03. [ ] `blockers.py` with fixtures and tests.
4. P04. [ ] `PortalAdapter` base and `demo_portal.py` adapter.
5. P05. [ ] Applier uses the adapter, HTTP path kept behind a flag.
6. P06. [ ] Headed handoff and resume.
7. P07. [ ] Screenshots on the Status screen.
8. P08. [ ] Re run all four failure injections and save new traces.

### Phase 2
1. P09. [ ] `autonomy_level` and `ai_policy` fields on listings, portal review template.
2. P10. [ ] Review and adapter for real portal 1 (Level 1).
3. P11. [ ] Review and adapter for real portal 2 (Level 1).
4. P12. [ ] Consent entries and audit log.
5. P13. [ ] Weekly canary job.
6. P14. [ ] Level 2 review screen in the app (filled values, screenshot, Approve button).

### Phase 3
1. P15. [ ] Listings table and admin review page.
2. P16. [ ] Collect, extract, validate pipeline with snippet checks.
3. P17. [ ] Refresh and expiry jobs.
4. P18. [ ] Curate 25 reviewed listings.

### Phase 4
1. P19. [ ] Authentication and per user data isolation tests.
2. P20. [ ] Postgres and migrations.
3. P21. [ ] Job queue and worker split (API, agent worker, browser worker).
4. P22. [ ] Encrypted storage and secrets manager.
5. P23. [ ] Deployment, monitoring, alerts, cost limits.
6. P24. [ ] Per user Telegram linking.
7. P25. [ ] Data export and delete.

### Phase 5
1. P26. [ ] Privacy policy, terms, consent screens, incident plan.
2. P27. [ ] Pilot with 10 to 20 users and a feedback log.
3. P28. [ ] Release evaluation set and regression gate.
4. P29. [ ] AI policy modes: `ai_policy` fields, Info and Draft Pack mode, Telegram briefing template, tests.

## 14. Risks and how we handle them

1. **A portal changes its layout**: label based locators, weekly canaries, automatic fallback to Level 0.
2. **A site bans automation or blocks us**: respect it, never evade it, move that listing to Level 0 and tell the user.
3. **Wrong listing data**: human review, verified dates, honest uncertainty in the UI.
4. **A false claim reaches a real application**: mandatory Verifier, user review before submit, audit trail, regression tests.
5. **Data leak of personal files**: encryption, isolation tests, minimal retention, incident plan.
6. **Provider bans or disputes about AI use**: the `ai_policy` field, Info and Draft Pack mode for restricted listings, and the user as the final author.
7. **LLM costs grow**: caching, limits, budget alarms, cheaper model for extraction and the stronger model only for Tailor and Verifier.
8. **Overpromising to users**: no guarantee of selection, clear status labels, honest confirmation rules.
9. **Burnout and scope creep**: ship Phase 1 and 2 first, pilot, then decide.

## 15. Things to verify before you build

1. [ ] Current Playwright for Python documentation: persistent contexts, headed mode, locators, install command.
2. [ ] Terms and robots rules of each real portal you target.
3. [ ] Current Nigerian data protection requirements and any registration duties for data controllers.
4. [ ] Your LLM provider's paid data processing terms.
5. [ ] Current payment provider options for Nigerian users.
6. [ ] Any AI use rules for each target scholarship.
