# 02_SCHEDULE_AND_BUILD_ORDER.md

All times Nigeria time (WAT). The hackathon starts Saturday October 10, 8:00 AM (12:30 PM IST). Submissions Monday October 12, 2:30 PM to 7:25 PM. Each of you has about 5 hours a day. Task ids refer to `13_TASKS_BACKEND.md` (B) and `14_TASKS_FRONTEND.md` (F). S tasks are shared setup tasks listed in section 6.

## 1. Saturday October 10: foundation and first slice

8:00 to 9:15 AM, setup (both):
1. S01 to S09 from section 6 (accounts, Entire, neatlogs, repo, keys, first commit, post 1).
2. Hard gate: do NOT start B01 until the Entire smoke test (S05) and the neatlogs trace test (S06) have passed or you have asked for help in Discord.

9:15 to 10:30 AM:
1. M: B01 skeleton, B02 tracing, B03 database.
2. A: F01 types and mocks, F02 layout and shared components.

10:30 AM to 1:00 PM:
1. M: B04 LLM wrapper, B05 failure flags, B06 persona and listings, B07 Intake, B08 Scout and Matcher.
2. A: F03 Upload and Profile screen, F04 Matches screen (against mocks).

1:00 PM checkpoint: `POST /api/profile/intake` then `POST /api/runs` returns real matches for the persona, and Ayo's Matches screen shows them. If not, stop adding features and fix this.

Evening buffer (30 minutes, async): post 2 (a real finding from the day).

## 2. Sunday October 11: the loop, the proof, the applier

9:00 AM to 10:30 AM (strict order):
1. M: B09 Researcher with cached dossiers, B10 Edge Finder, B11 baseline Tailor.
2. A: F05 switch to the real backend, fix contract mismatches.

10:30 AM to 12:30 PM:
1. M: B12 Verifier audit only, B13 Coordinator v1 and `run_pipeline.py`.
2. M: B14 RUN A. Run mode A twice. Save numbers and trace links BEFORE writing enforcement.
3. A: F06 Application Status screen.

12:30 to 2:00 PM:
1. M: B15 Verifier enforce loop, B16 RUN B, B17 improvement loop 1 with the neatlogs MCP (or by hand).
2. A: F07 portal templates.

Evening block (7:00 to 9:00 PM, both):
1. M: B18 notifications, B19 package builder, B20 portal backend, B21 Applier (if not finished in the afternoon, finish now).
2. A: F08 Handoff screen, F09 polish.
3. B: B22 failure injection runs and recovery decision spans, B23 Challenger, N tasks for neatlogs depth (see B24).
4. B: cfo.ai plan from real data (`16_CFO_AND_CRUSTDATA.md`).
5. FEATURE FREEZE at 9:00 PM. After that only bug fixes.
6. Posts 5 to 8 as things happen.

If the Applier is not working by 9:00 PM Sunday, cut in this order: email path, then Challenger, then Info and Draft Pack mode. Keep the portal path and the CAPTCHA handoff.

## 3. Monday October 12: proof and submit

1. 8:00 to 9:00 AM: B25 final clean full run on the persona (mode B), a backup screen recording, final bug fixes.
2. 9:00 to 11:00 AM: rehearse once, RECORD the demo (`18_DEMO_SCRIPT.md`), trim under 3 minutes.
3. 11:00 AM to 1:00 PM: README (`20_README_TEMPLATE.md`), evidence file complete (`17_EVIDENCE_CHECKLIST.md`), Entire screenshots and graph output, cfo.ai page link, repo cleanup, secrets check.
4. 1:00 to 2:30 PM: upload the video, run the final disqualification check, draft the quote post.
5. 2:30 PM: submit with the Submit on X button. Own hard deadline 6:00 PM. Official cutoff 7:25 PM.

## 4. Cut order if you fall behind

1. Live Crustdata research on camera (use cached dossiers).
2. Info and Draft Pack mode.
3. Telegram polish and gap questions.
4. Email path.
5. Challenger.
6. Run C and the second improvement loop (keep the first loop).
7. Evaluation script, comments, extra neatlogs views.

NEVER cut: Verifier audit and enforce, run A and run B, the recovery runs, the portal with the CAPTCHA handoff, Entire commits, the evidence file, the demo.

## 5. Checkpoints (go or no go)

1. Saturday 9:15 AM: Entire creates a checkpoint, a neatlogs trace shows a nested span tree, the Gemini call works. If not, fix before anything else.
2. Saturday 1:00 PM: persona to matches works end to end.
3. Sunday 12:30 PM: run A captured. If the Tailor does not run yet, simplify the Tailor, never skip run A.
4. Sunday 4:00 PM: run B captured with numbers.
5. Sunday 9:00 PM: feature freeze, a full run completes with at least one submitted and one handed off application.
6. Monday 1:00 PM: evidence complete, video uploaded.

## 6. Shared setup tasks (S)

1. S01. B: confirm all 4 teammates registered on Luma with the SAME team name. Complete web check in. Join the Discord. (5 min)
2. S02. M: create the public GitHub repo AFTER 8:00 AM, clone on both machines. (5 min)
3. S03. M: install the Antigravity CLI and Entire, confirm `antigravity` appears in the Entire agent list. (15 min, `03_TOOLS_SETUP.md` section 2)
4. S04. M: enable Entire in the repo BEFORE the first commit. (5 min)
5. S05. M: Entire smoke test (a tiny change through the Antigravity CLI, commit, confirm the checkpoint exists and the checkpoints branch is pushed). (10 min)
6. S06. M: neatlogs account, key, doctor check, one hello trace. (15 min, `03_TOOLS_SETUP.md` section 3)
7. S07. M: Gemini key and model test, fallback provider key, Telegram bot, Gmail app password. (20 min)
8. S08. M: cfo.ai signup and immediate cancel, Crustdata credits claimed. (10 min)
9. S09. M: copy the pack files and rule files into the repo, first commit and push, post 1. (10 min)
10. S10. A: repeat Entire setup on Ayo's machine and create the Next.js app. (20 min)
