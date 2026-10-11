# 17_EVIDENCE_CHECKLIST.md

Every piece of proof the judges need. Copy this file to the repo root as `EVIDENCE.md` and fill each blank with a real link, screenshot path or number as it is produced. Screenshots go in `docs/evidence/screenshots/` with clear names. Never fabricate or edit evidence. If something did not work, write what happened.

Submission window: Monday October 12, 2:30 PM to 7:25 PM Nigeria time. Late submissions are not judged. Our own deadline: 6:00 PM.

## 1. Repo basics

1. [ ] Public repo URL: ______
2. [ ] First commit timestamp (must be after Saturday 8:00 AM Nigeria time): ______
3. [ ] Commit counts Saturday / Sunday / Monday: ______ / ______ / ______
4. [ ] All code written during the hackathon (no pasted pre existing code): ______
5. [ ] No secrets or real personal data in the repo (checked on ______ by ______)
6. [ ] No field in `listings.json` contains the word REPLACE: ______
7. [ ] README explains setup, architecture, limitations and has the neatlogs section: ______

## 2. neatlogs: run A versus run B

1. [x] Run A traces (before enforcement): files `docs/evidence/run_A_1.json`, `docs/evidence/run_A_2.json`
2. [x] Run B traces (after): files `docs/evidence/run_B_1.json`, `docs/evidence/run_B_2.json`, table `docs/evidence/comparison_table.md`
3. [x] Comparison from real data (each mode run twice, median values):
   1. Claims total: A 16 | B 16
   2. Unsupported before enforcement: A 16 | B 16
   3. Unsupported in final output: A 16 | B 0 (-100%)
   4. Overturned by self challenge: A 0 | B 0
   5. Sourced personal references: A 1 | B 1
   6. Tokens per application: A 0 | B 0 (demo client)
   7. Cost per application (USD): A 0.00 | B 0.00
   8. Latency per application (seconds): A 0.00 | B 0.00
   9. Recovery decisions and retries: A 0 | B 0
4. [x] One paragraph "what we changed and why": In Mode A, single-pass audit only counted unsupported claims without modifying drafted text, leaving 16 hallucinated/unsupported claims in final output. In Mode B (Task B15), we introduced verify_mode_b: up to 2 targeted revision rounds via tailor_revise, a deterministic segment removal fallback marking status='removed' and logging RemovedClaim, adversarial challenger verification, and sensitive post-scan. This drove unsupported claims in the final submitted package from 16 down to exactly 0.
5. [ ] Span tree screenshot of one full application: ______
6. [ ] GUARDRAIL Passed and Blocked screenshots: ______
7. [ ] Analytics views (cost by agent, tool errors): ______
8. [ ] Which tag comparison method was used (side by side or filtered views): ______

## 2b. neatlogs depth

1. [ ] Recovery decision span screenshots with reasons, one per failure type: ______
2. [ ] A real overturned claim (original text, reason): ______
3. [ ] `docs/evidence/improvement_log.md` with 2 loops (trace link, finding, commit hash, Entire checkpoint, numbers): ______
4. [ ] Antigravity reading a trace through the neatlogs MCP (screenshot), or the manual alternative explained: ______
5. [ ] Detections list and traces list with badges: ______
6. [ ] Investigate thread with linked evidence: ______
7. [ ] Session Replay of the CAPTCHA handoff (optional): ______
8. [ ] Evaluation table `eval_v1` and `eval_v2`: ______
9. [ ] Votes and a comment thread screenshot: ______
10. [ ] The View trace (or Open neatlogs) button in the app, and how `trace_url` is built: ______

## 3. Recovery runs (each labeled as injected)

For each: what failed, what the agent did next (the decision and reason), trace link, screenshot.
1. [ ] `llm_429`: ______
2. [ ] `bad_json`: ______
3. [ ] `portal_500`: ______
4. [ ] `captcha_wall` (blocker, handoff message, Done, confirmation code): ______
5. [ ] `research_down`: ______
6. [ ] `smtp_fail`: ______
7. [ ] `injection_page`: ______
8. [ ] A real (not injected) failure we hit and how the agent or we handled it: ______

## 4. Verification evidence

1. [ ] A real unsupported claim caught (original text, check result, final text): ______
2. [ ] Final verification report for the persona with zero unsupported claims: ______
3. [ ] Trap checks passed: assistant coordinator not upgraded to president, no years of experience claim, sensitive fact never used: ______
4. [ ] Unit test output for `sensitive.py`, the deterministic check and the trap tests: ______

## 5. Entire

1. [ ] Entire enabled before the first commit (status output screenshot): ______
2. [ ] Antigravity CLI used for coding sessions, and what the smoke test showed: ______
3. [ ] Checkpoints branch link on GitHub: ______
4. [ ] Checkpoint list screenshots: Saturday ______ Sunday ______ Monday ______
5. [ ] One checkpoint opened (Sessions and Changes tabs) for the Verifier change, commit hash ______, AI percentage ______
6. [ ] `entire graph` impact or diff output file or screenshot: ______ (stats output labeled as an estimate)
7. [ ] Note on commits made without checkpoints: ______

## 6. cfo.ai

1. [ ] Signup done, subscription cancelled (screenshot): ______
2. [ ] Pricing and margin view: ______
3. [ ] Cost per application from neatlogs and the number used: ______
4. [ ] Three scenarios, runway and break even: ______
5. [ ] Shared read only Page link (and password if any): ______
6. [ ] `docs/evidence/business_plan.md`: ______

## 7. Telegram and submission paths

1. [ ] Telegram messages for each status change on a real phone (screenshots): ______
2. [ ] Email received in the demo inbox: ______
3. [ ] Portal submission confirmation code: ______
4. [ ] CAPTCHA handoff flow (message, Handoff screen, Done, confirmation): ______
5. [ ] A real listing ending as a prepared package (and the restricted listing briefing if built): ______

## 8. Build in public (#neatHack), at least 6 posts

Organic, with real screenshots, public, tagged. Post links:
1. [ ] Post 1 kickoff: ______
2. [ ] Post 2 first real finding: ______
3. [ ] Post 3 researcher and sources: ______
4. [ ] Post 4 run A finding: ______
5. [ ] Post 5 run B and the MCP loop: ______
6. [ ] Post 6 CAPTCHA handoff: ______
7. [ ] Post 7 recovery decisions: ______
8. [ ] Post 8 cfo.ai plan: ______
9. [ ] Post 9 submission: ______

## 9. Demo video

1. [ ] Link: ______ Length (3 minutes or less): ______
2. [ ] neatlogs visible in the first 20 seconds: ______
3. [ ] Covers neatlogs, Entire and cfo.ai each with architecture, implementation, runtime, reasoning, result: ______
4. [ ] Shows a live or recent run, a failure and recovery, and verification: ______
5. [ ] Backup recording saved: ______

## 10. Team and participation

1. [ ] 4 registered members with the same team name on Luma: ______
2. [ ] Who built what (Memeshi backend and agents, Ayo frontend and portal): ______
3. [ ] Confirmed the rules on registered members who are not building: ______
4. [ ] Asked in Discord how judges view neatlogs traces (and the answer): ______

## 11. Submission

1. [ ] Official neatlogs post link we quote: ______
2. [ ] Quote post includes team name, project name, public repo link, demo video link.
3. [ ] Posted with the Submit on X button (opening the draft alone does not submit).
4. [ ] Our quote post link: ______ Posted at (Nigeria time): ______
5. [ ] Checked from a logged out browser that the post is public and links work: ______

## 12. Final disqualification check (Monday 1:00 PM)

1. [ ] No code before the start time.
2. [ ] neatlogs, Entire and cfo.ai all used and shown.
3. [ ] No bought or fake engagement.
4. [ ] No secrets, no real personal data, no REPLACE in listings.
5. [ ] Submission posted inside the window.
