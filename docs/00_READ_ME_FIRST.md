# 00_READ_ME_FIRST.md

ScholarPilot, neatHack edition. This is version 2 of the pack. It replaces every earlier file. Use ONLY the files in `pack_v2`.

Written for two people: Memeshi (agents and backend) and Ayo (design and frontend), using Google Antigravity as the only coding agent.

## 1. Honest note about "no mistakes"

No document can guarantee an AI coding agent writes perfect code. What this pack does instead:
1. It removes guesswork: exact files, exact function names, exact data shapes, exact prompts, exact order.
2. Every task card has acceptance tests you can run in minutes, so mistakes are caught immediately and not at 2 AM on Monday.
3. It avoids fragile dependencies and clever designs on purpose.

If Antigravity deviates from a spec, do not argue. Paste the fix prompts from `12_ANTIGRAVITY_RULES.md` section 6.

## 2. The files, in the order you should use them

Read in this order. The first column says WHEN.

1. NOW (before Saturday 8:00 AM, reading only): `00`, `01`, `02`, `03`.
2. SATURDAY 8:00 AM setup: `03_TOOLS_SETUP.md` (do every step), `12_ANTIGRAVITY_RULES.md` (create the rule files).
3. BEFORE EACH TASK: the task card in `13_TASKS_BACKEND.md` (Memeshi) or `14_TASKS_FRONTEND.md` (Ayo). The card tells you which spec files to point Antigravity at.
4. SPEC FILES (Antigravity reads these, you skim them): `04_ARCHITECTURE.md`, `05_DATA_MODELS.md`, `06_API_CONTRACT.md`, `07_AGENTS_SPEC.md`, `08_PROMPTS.md`, `09_NEATLOGS_SPEC.md`, `10_FAILURES_AND_RECOVERY.md`, `11_DEMO_PORTAL_AND_SYNTHETIC_DATA.md`.
5. AYO ONLY: `15_DESIGN_BRIEF.md` and `14_TASKS_FRONTEND.md`.
6. SUNDAY EVENING: `16_CFO_AND_CRUSTDATA.md`.
7. ALL WEEKEND: `17_EVIDENCE_CHECKLIST.md` (fill as you go).
8. MONDAY: `18_DEMO_SCRIPT.md`, `19_POSTS.md`, `20_README_TEMPLATE.md`.
9. AFTER THE HACKATHON ONLY: `21_PRODUCTION_UPGRADE.md`.
10. REFERENCE: `22_TOOLS_RESEARCH_REFERENCE.md`, `23_FAILURE_PLAYBOOK_REFERENCE.md`.

## 3. What to build first (the strategy)

Build a thin working slice end to end FIRST, then deepen it. Do not perfect any one agent before the whole chain runs.

1. **Setup and smoke tests (Saturday 8:00 to 9:15 AM).** Entire capturing, neatlogs trace visible, keys working, repo public, first commit. Nothing else matters until these work.
2. **The skeleton (B01 to B05).** Health endpoint, tracing, database, the LLM wrapper, failure flags. These are the foundation every agent uses. The LLM wrapper is the most important single file.
3. **Data in (B06 to B09).** Synthetic persona, listings file, Intake, Scout, Matcher. First visible result: the persona goes in, ranked scholarships come out on Ayo's Matches screen.
4. **Research, evidence, writing (B10 to B13).** Researcher with cached dossiers, Edge Finder, baseline Tailor. First full chain to a written application with NO verification.
5. **Verification and the proof (B14 to B18).** Verifier audit only, Coordinator, then RUN A (before), then Verifier enforcement, then RUN B (after). This is the heart of the score.
6. **Submitting (B19 to B24).** Notifications, package builder, demo portal, Applier, handoff, resume.
7. **Break it on purpose (B25 to B28).** Failure injection, recovery decisions, challenger, deep neatlogs.
8. **Proof and submission (Monday).** Final clean runs, evidence, demo recording, README, submit.

Frontend runs in parallel against mock data and switches to the real API as backend endpoints appear (`14_TASKS_FRONTEND.md`).

## 4. The one sentence pitch (use everywhere)

ScholarPilot is an agent that finds scholarships you qualify for, researches the school, picks your real evidence, verifies every claim, then applies or hands off.

## 5. Judging weights and what each file serves

1. The agent (30 percent): files 04 to 08, 10, 11.
2. Use of neatlogs, Entire and cfo.ai (25 percent): files 03, 09, 16, 17.
3. Demo video (20 percent): files 18, 17.
4. Building in public (15 percent): file 19.
5. Usefulness and originality (10 percent): files 01, 11.

## 6. The ten rules that cannot break

1. No application code committed before Saturday October 10, 8:00 AM Nigeria time (12:30 PM IST). Planning documents are fine.
2. Entire enabled BEFORE the first commit, on both machines. Code is written through the Antigravity CLI so sessions are captured.
3. All three required tools are really used and shown: neatlogs, Entire, cfo.ai.
4. Never invent applicant content. Never bypass a CAPTCHA. Never submit to a real scholarship portal.
5. Never commit secrets or real personal data. The public repo uses the synthetic persona only.
6. Every number in the demo comes from a real run. Injected failures are labeled as injected.
7. No bought or fake engagement.
8. All four members registered on Luma with the SAME team name.
9. Submit with the Submit on X button during the window (Monday 2:30 PM to 7:25 PM Nigeria time). Our own deadline is 6:00 PM.
10. Commit small and often with the commit format in `12_ANTIGRAVITY_RULES.md`.

## 7. Conventions used across the pack

1. Dates are strings `YYYY/MM/DD`. Date times are `YYYY/MM/DD HH:MM:SS` in UTC.
2. Ids: facts `C1`, `T1`, `P1`; dossier facts `D1`; edges `E1`; claims `CL1`; gaps `G1`; applications `app_1`; runs `run_YYYYMMDD_NNN` (digits and underscores).
3. Span kinds are uppercase: WORKFLOW, AGENT, CHAIN, TOOL, RETRIEVER, EMBEDDING, GUARDRAIL, MCP_TOOL.
4. The pack avoids dash characters in names so nothing is mistyped. Environment variables and file names use underscores.
5. Anything marked VERIFY needs a quick test. Write the result in the blank.
6. Memeshi is M, Ayo is A, both is B.
