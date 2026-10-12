# ScholarPilot reality audit — 2026/10/12

The active root v1 implementation is a bounded tool-using agent inside a predefined workflow. Real model calls choose research/evidence order and source selection, draft and judge text, and request revisions. The loop has four tools and six decisions maximum. This is sufficient to call it an agent; it is not a general autonomous scholarship operator. Human approval is an optional user mode, not the definition of an agent.

## Active demonstration

| Component | Actual behavior | Remaining demo or limitation |
| --- | --- | --- |
| Applicant | 33 reviewed source facts persisted in PostgreSQL | Fictional Tobi fixture and synthetic documents; no real applicant validation |
| Discovery | Eligibility and ranking against actual database rows | Launcher seeds one owned portal listing; no live scholarship discovery |
| Matching | Deterministic rules | Fixed heuristic weights; fit/strength scores are not calibrated eligibility probabilities |
| Research | Real HTTP fetch with retained page text | Fictional university page; public live research off; no multi-source search or persistent research memory |
| Decisions/drafting | Real Gemini calls and allowlisted tools; independent judge and Challenger calls | Judges can agree on an error; two revisions and six decisions bound capability; same vendor fallback |
| Frontend | Real v1 API calls, mocks disabled | Static `frontend/mocks` and demo persona handlers remain for original/demo mode; v1 does not use their submitted state |
| Infrastructure | Real API, worker, PostgreSQL 16.11, Redis 7.4.9 and Chromium | Local development processes, privileged database role; deployment not validated |
| Submission | Real filled form and authoritative receipt | Owned fictional portal only; no arbitrary portal adaptation or real scholarship submission |
| Notifications | Delivery integrations exist | External Telegram/email disabled locally; mock Telegram success path exists when no token; not evidence of real delivery |
| Neatlogs | Actual wrapped model calls, trace readback, six detectors and actual Replay | Investigate summary connection failure; Evals/Fixes dispatch/prompt promotion not exercised; selective MCP paging unavailable |
| Browser test doubles | `mock_mode=False` on active job | Simulated screenshots/confirmation branch still exists for tests; never use it as application evidence |

The original SQLite `/api` implementation and the root PostgreSQL `/v1` implementation both remain in the repository. The active frontend uses v1; the original backend supplies the owned portal. Defaults outside `start --agent` remain extractive (`AGENT_ENABLED=false`, `LLM_DRAFTING=false`). No model output is silently substituted when the explicit live agent path fails. Source fact review is still required at onboarding.

## What should come next, in order

1. Validate decisions and factuality across a diverse fictional evaluation set: measure unsupported claims, rejected valid claims, tool misuse, costs, failure recovery and duplicate submissions. The first source-review incident proved that agreeing judges are not enough.
2. Add genuine scholarship discovery and multi-page institutional research, with source freshness, deadlines, provenance and blocked-page handoff. Currently the catalogue is imported, not discovered autonomously.
3. Give the agent a richer but bounded action space: search again, request missing applicant evidence, revise selected evidence, choose a different opportunity and explain why it stopped. Currently research failure may leave zero evidence and the loop cannot invent a new recovery strategy.
4. Persist investigation/research checkpoints beyond process memory and handle cancellation, restart, budget exhaustion and uncertain outcomes in repeatable integration tests. Existing application events already preserve some checkpoints; there is no broad learning or durable long-term agent memory.
5. Finish actual notification delivery, verified identity onboarding, private deployment/operations and portal adapter validation. Real portal submission remains prohibited by the current project instructions; it would need an explicit scope/spec change and permitted integrations. Login/CAPTCHA remains a human handoff.

Autopilot is enabled by default for new users and now honored by the planner. The existing Profile checkbox can select Review. The owner pause marker is checked before automatic Submit, but there is a race interval between that check and remote acceptance. Turning off cannot undo a received application or cancel a model request already in flight. Evidence: `evidence/autopilot_e2e_20261012.json`, actual receipt **DEMO2985**, no approval event. This trace contains recovered provider errors and is marked error by Neatlogs; report that alongside the successful receipt.
