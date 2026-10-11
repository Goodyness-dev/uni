# 01_PROJECT_AND_SCOPE.md

## 1. What we build

ScholarPilot: an agent that finds scholarships you qualify for, researches the school, picks your real evidence, verifies every claim, then applies or hands off.

Working name only. Keep the name consistent in the UI, README and posts.

## 2. The problem

Strong students, especially in Nigeria and across Africa, lose scholarships because applications need days of research and rewriting, and generic applications lose to personalized ones. Tools that tailor a CV with an LLM often invent achievements, which can get an applicant disqualified. We solve both: deep personalization with zero invention.

## 3. Hackathon fit (track: Build an agent that works, literally)

1. Planning: the Coordinator orders scholarships by fit and deadline.
2. Tool use: file reads, a research tool, email, an HTTP form submission, Telegram.
3. State: every application has a persisted status in SQLite and survives a restart.
4. Context: three grounding sources (CV facts, Profile Vault facts, research dossier) reach the right agent at the right time.
5. Execution: raw uploads to a confirmed submission or a ready package with no human in the loop, except a CAPTCHA handoff.
6. Recovery: rate limits, bad JSON, portal errors, CAPTCHA walls and unreachable research each have a defined recovery that is logged with a reason.
7. Verification: every generated claim is checked against its source, then challenged by a second skeptical pass.
8. Iteration: the verifier loop, and the measured improvement from run A to run B (and run C).

## 4. User inputs

1. CV (PDF or pasted text).
2. Transcript (pasted text).
3. Preferences form: level (undergraduate, masters, phd), fields, countries, funding (full or partial), start year.
4. Profile Vault: a personal file with sports, volunteering, certifications, leadership, awards, projects, languages, hardships, career goals, why abroad. Either guided form sections or free text. Plus a consent flag for sensitive facts.

## 5. User flow

1. Upload and fill the profile. Intake turns everything into numbered facts (`C1`, `T1`, `P1`).
2. Press Run agent. The Coordinator starts a run.
3. Scout loads `listings.json`. Matcher applies hard rules and scores fit. The Matches screen shows them.
4. For the top 2, Researcher builds a sourced dossier.
5. Edge Finder compares dossier and criteria with the applicant's facts and selects the top edges automatically. No approval step.
6. Tailor writes the CV summary, selected CV bullets and one essay answer.
7. Verifier checks every claim in a loop of up to 2 rounds, then the Challenger tries to disprove the claims. Unsupported claims are removed and flagged.
8. Applier routes by channel: email, demo portal form, demo portal with CAPTCHA (handoff), or package only for real scholarships.
9. The user gets a Telegram message at each step, and sees everything on the Application Status screen.

## 6. Scope (must have)

1. Intake, Scout, Matcher, Researcher, Edge Finder, Tailor, Verifier (audit, enforce, challenger), Applier, Coordinator.
2. SQLite state and resumable runs.
3. Telegram notifications and the Done handoff.
4. Demo portal with a CAPTCHA toggle.
5. Failure injection with logged recovery decisions.
6. Run modes A and B with metrics. Run C after the second improvement loop.
7. Four UI screens plus portal pages.
8. neatlogs depth (spec in `09_NEATLOGS_SPEC.md`), Entire checkpoints, cfo.ai plan, evidence, demo, posts.

## 7. Non goals (do NOT build)

1. Live scraping of scholarship sites.
2. Accounts, login, multi user.
3. Real submissions to any real portal.
4. Solving or bypassing CAPTCHAs.
5. Docker, deployment, CI.
6. More than one essay prompt per scholarship.
7. Perfect PDF parsing.
8. Playwright (it is in `21_PRODUCTION_UPGRADE.md`, after the hackathon).
9. Real people's data anywhere in the repo.

## 8. Channels and autonomy

Channels (field `channel` on each listing):
1. `email`: send the application email with attachments to our own inbox (mock listing only). Fully automatic.
2. `portal_form`: submit to our demo portal over HTTP. If the CAPTCHA flag is on, the Applier detects the blocker and hands off.
3. `portal_captcha`: the demo portal listing where the CAPTCHA is ALWAYS on (guarantees the handoff demo).
4. `package_only`: all real scholarships. We prepare a package and never submit.

## 9. AI policy handling (keep simple for the hackathon)

Each listing has `ai_policy`: `allowed`, `disclose`, `restricted` or `unknown`. Hackathon rule: all listings are `allowed` or `disclose` except one real listing set to `restricted` to demonstrate Info and Draft Pack mode (see `07_AGENTS_SPEC.md` section 9). If you run out of time, cut that mode first.

## 10. Definition of done

1. [ ] A fresh clone starts with two commands per side and a complete `.env.example`.
2. [ ] The persona runs end to end: upload, matches, research, edges, writing, verification, application outcome.
3. [ ] One application submitted and confirmed on the demo portal, one by email, one handed off for a CAPTCHA then resumed and confirmed.
4. [ ] Run B final output has zero unsupported claims. Run A metrics saved for comparison.
5. [ ] Each injected failure has a recorded run with the recovery decision visible.
6. [ ] Telegram messages received on a real phone for every status change.
7. [ ] neatlogs: traces for run A, B and the recovery runs, detections created, improvement log with 2 loops.
8. [ ] Entire checkpoints exist for the history, graph output captured.
9. [ ] cfo.ai plan built from real cost per application, shared as a read only Page.
10. [ ] Demo video under 3 minutes with neatlogs visible in the first 20 seconds.
11. [ ] At least 6 public #neatHack posts with links in the evidence file.
12. [ ] No secrets or real personal data in the repo. All commits inside the hackathon window.
13. [ ] Submitted on X before 6:00 PM Monday.

## 11. Honesty statements shown in the product

1. Every generated sentence has source pills (CV fact, transcript fact, Vault fact, programme fact).
2. Mock listings are labeled DEMO LISTING and the portal DEMO PORTAL.
3. The app says that documents are sent to an AI provider.
4. No guarantee of selection is ever implied.

## 12. Stretch (only after the definition of done)

1. Live Crustdata research on camera.
2. LLM chosen recovery with a whitelist.
3. Deadline reminders.
4. A second essay prompt.
5. Run mode Z (no research, no edges) to show the full improvement.
