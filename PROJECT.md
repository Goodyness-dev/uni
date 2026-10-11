# PROJECT.md

Working name: **ScholarPilot** (rename freely, but keep the name consistent in the UI, README and posts).

## 1. One line

An autonomous agent that finds scholarships you qualify for, researches each school and program, finds your strongest evidence from your own life file, writes a tailored application with every claim verified, and submits or prepares it, telling you on Telegram at every step.

## 2. The problem

Strong students, especially in Nigeria and across Africa, lose scholarships because applications take days of research and rewriting, and generic applications lose to personalized ones. Tools that "tailor" a CV with an LLM often invent achievements, which is dangerous in an application. We solve both: deep personalization and zero invention.

## 3. Hackathon fit

Track: "Build an agent that works (literally)". We demonstrate planning, tool use, state, context, execution, recovery, verification and iteration:

1. Planning: the Coordinator ranks scholarships by fit and deadline and plans the order of work.
2. Tool use: file reads, a research tool, SMTP email, an HTTP form submission to a portal, the Telegram Bot API.
3. State: every application has a persisted status in SQLite and survives a restart.
4. Context: three grounding sources (CV facts, Profile Vault facts, research dossier) are passed to the right agent at the right time.
5. Execution: the run goes from raw uploads to a confirmed submission or a ready package without a person in the loop (except a CAPTCHA handoff).
6. Recovery: LLM rate limits, malformed output, portal errors and CAPTCHA walls each trigger a defined fallback.
7. Verification: the Verifier checks every generated claim against its source.
8. Iteration: the Tailor and Verifier loop (max 2 rounds), plus the measured improvement from run A to run B.

## 4. Users

Primary demo user: a fictional Nigerian computer engineering graduate applying for Master's scholarships abroad. The design is general (any country, any level) but the demo and the listings target Nigerian and African applicants.

## 5. Inputs from the user

1. **CV** (PDF or pasted text).
2. **Transcript** (pasted text or PDF text, grades and courses).
3. **Preferences form**: target level (Master's, PhD, undergraduate), fields of study, countries of interest, minimum funding they need (full, partial), earliest start date.
4. **Profile Vault**: a personal file with as much life detail as possible, either filled through the guided form or pasted as free text. Sections: sports and teams, volunteering (role, hours, impact), certifications, leadership, awards, projects, languages, hardships overcome, career goals, why they want to study abroad, plus a consent flag for sensitive facts.

## 6. User flow (what the demo shows)

1. User opens the app and uploads CV and transcript, fills the short preferences form, and submits their Profile Vault.
2. Intake turns all of it into numbered facts (for example `C14` for CV, `P7` for Vault, `T3` for transcript).
3. User presses "Run agent". The Coordinator starts a run.
4. Scout loads the local listings file. Matcher filters by hard rules and scores fit. The Matches screen shows scores and reasons.
5. For the top 2 matches, the Researcher builds a sourced dossier (school, program, professors, scholarship priorities).
6. The Edge Finder compares the dossier with the user's facts and automatically selects the top edges (no approval step).
7. The Tailor writes a tailored CV summary, tailored bullet selection and one essay answer using the selected edges.
8. The Verifier checks each claim and loops with the Tailor up to 2 rounds. Unsupported claims are removed and flagged.
9. The Applier routes each application by channel:
   1. Email channel: sends the application email with attachments to our own inbox (demo) and waits for the send receipt.
   2. Demo portal without CAPTCHA: fills and submits the form over HTTP, then reads the confirmation code.
   3. Demo portal with CAPTCHA: detects the blocker, stops, saves the package, sends a Telegram handoff with a link, and waits.
   4. Real scholarship portals: never automated. Produces a ready to submit package and a checklist.
10. The user solves the CAPTCHA on the portal page and taps Done. The Applier confirms the submission and marks it submitted.
11. Telegram messages arrive at: matches found, researched, tailored and verified, submitted, awaiting you, failed, deadline within 48 hours.
12. The Status screen shows each application, its status, the edges used (read only) and the verification report.

## 7. Scope (must have)

1. Intake of CV, transcript, preferences and Vault into numbered facts.
2. Local listings file with 5 entries (3 real, hand copied from official pages, and 2 clearly labeled mock entries that point to our demo portal and demo email).
3. Scout, Matcher, Researcher, Edge Finder, Tailor, Verifier, Applier, Coordinator.
4. SQLite state, resumable runs.
5. Telegram notifications and the Done button handoff.
6. Demo portal with a CAPTCHA toggle.
7. Failure injection flags and the defined recoveries.
8. Run mode A (no enforcement) and run mode B (enforcement) with metrics.
9. Four UI screens (see section 9).
10. Full neatlogs tracing, Entire checkpoints, cfo.ai plan, evidence file, demo video, posts.

## 8. Non goals (do NOT build)

1. Live scraping of scholarship websites.
2. User accounts, login, multi user support.
3. Real submissions to any real scholarship portal.
4. Solving or bypassing CAPTCHAs, rotating proxies, stealth browsers.
5. Docker, cloud deployment, CI pipelines.
6. More than one essay prompt per scholarship.
7. Perfect PDF parsing (a basic text extract plus paste fallback is enough).
8. A mobile app, payments, or a database server.
9. Using real people's data. The public repo and demo use the synthetic persona only.

## 9. UI screens (4)

1. **Upload and Profile**: file inputs, preferences form, Profile Vault guided form with free text box, consent checkbox for sensitive facts, "Run agent" button, list of parsed facts (editable).
2. **Matches**: ranked cards with fit score, reasons, deadline, channel badge, and a "Research and apply" status.
3. **Application Status**: per application timeline of events, status badge, edges used (read only with fact id and source), verification report (claims, verdicts, removed claims), tailored documents preview, notification log.
4. **Handoff**: shown when an application is awaiting the user. Explains the blocker, shows the package download links, the portal link, and a Done button.

## 10. Definition of done

The project is done when ALL of the following are true:

1. [ ] A fresh clone starts with two commands (backend and frontend) and a documented `.env.example`.
2. [ ] The synthetic persona runs end to end: upload, matches, research, edges, tailored output, verification, application outcome.
3. [ ] At least one application is submitted and confirmed on the demo portal, one by email, and one is handed off for a CAPTCHA and then resumed and confirmed.
4. [ ] Verification report shows zero unsupported claims in the final output of run B, and run A has its metrics saved for comparison.
5. [ ] Each injected failure (llm_429, bad_json, portal_500, captcha_wall) has a recorded run showing the recovery.
6. [ ] Telegram messages are received for every status change on a real phone.
7. [ ] neatlogs shows complete traces for run A, run B and the recovery run.
8. [ ] Entire checkpoints exist for the commit history, and the graph output is captured.
9. [ ] cfo.ai plan is built from real cost per application and is included in the submission.
10. [ ] Demo video under 3 minutes covers neatlogs, Entire and cfo.ai explicitly.
11. [ ] At least 6 public #neatHack build in public posts exist, and links are in `EVIDENCE.md`.
12. [ ] No secrets or real personal data in the repo. All commits dated within the hackathon.
13. [ ] Submitted on X before our own deadline of Monday 6:00 PM Nigeria time.

## 11. Honesty statements to show in the product

1. Every generated sentence has a "source" pill in the UI (CV fact, Vault fact or dossier link).
2. Mock listings are labeled "DEMO LISTING".
3. The app tells users their data is sent to an LLM provider.

## 12. Stretch (only after everything above is done)

1. Live research on camera instead of cached dossiers.
2. Playwright driven form fill on the demo portal (the default uses plain HTTP).
3. A deadline reminder scheduler.
4. A second essay prompt.
5. Deploying the frontend.
