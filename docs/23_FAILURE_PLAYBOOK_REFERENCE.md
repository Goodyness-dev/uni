# FAILURE_PLAYBOOK.md

> Pack v2 note: reference only. The working rules are in `10_FAILURES_AND_RECOVERY.md`. Older file names mentioned here map to the v2 files.


Every failure we are likely to hit while building and running ScholarPilot, how it shows up in neatlogs, and how to fix and prevent it. Built from the neatlogs docs (Traces, Detections, Investigate, Fixes, Analytics, Evals, Session Replay, Comments, Tools and MCPs, SDK Doctor) and from our own architecture.

Read it with `NEATLOGS_DEEP_USE.md` (the upgrades) and `ARCHITECTURE.md` section 8 (recovery rules).

## 1. The neatlogs toolbox, matched to jobs

1. **Traces (span tree and timeline):** see exactly what a step received and returned. The timeline shows which step dominated time, whether work really ran in parallel, and where idle gaps are. Best for: slow runs, wrong outputs, retry storms.
2. **Span detail:** the exact prompt sent to the model (after templates and formatting), token breakdown, model and provider, latency, plus our custom attributes. Best for: prompt bugs, context bloat, wrong model after a fallback.
3. **Per trace AI assistant:** ask "why did the agent not call the tool" or "what context did the second LLM call get" and get answers grounded in that run.
4. **Voting:** thumbs up or down on a span's output, stored per span and filterable. Best for: building a labeled set of good and bad essays and Tailor outputs while we debug.
5. **Comments:** pin a note to a span with a highlight, tag a teammate. Best for: Ayo and Memeshi discussing a finding in place.
6. **Detections:** four rule types (regex, condition, PII, classifier) that flag spans and show as badges in the traces list. Best for: scanning dozens of runs at a glance (section 2).
7. **Investigate (Neat AI):** ask in plain English, in Fast mode or Pro mode, and it runs a multi step investigation across traces with linked evidence, then can propose a fix. Threads are stateful, so follow ups work. Best for: "why do so many runs have negative detections" style questions (section 5).
8. **Fixes:** AI generated fix suggestions with root cause analysis, from failing traces or investigations. Dispatching a fix to a coding agent that opens a pull request may depend on the agent supported, so VERIFY it works for our setup. The reliable route for us is the MCP server into Antigravity.
9. **Analytics:** cost, latency, errors, tool usage and detection trends across runs. Best for: spotting which agent or tool costs most or fails most.
10. **Evals:** send real traces to human reviewers, AI evaluators or both and aggregate the judgments. Best for: scoring essay quality and personalization quality (VERIFY availability for our plan).
11. **Session Replay (experimental):** play back one run step by step. Today one trace equals one session, so do NOT rely on multi trace sessions (this corrects `NEATLOGS_DEEP_USE.md` U6, use run tags and attributes to group runs instead). Good for the CAPTCHA handoff demo.
12. **Tools and MCPs (Settings):** connect GitHub, Linear, Slack or Notion so Neat Agent can read the repo file or issue while investigating. Connect GitHub for our repo so fixes are grounded in the real source. Each teammate connects their own account.
13. **SDK Doctor:** local check that the install and span envelope are right, then a hosted probe that the trace survives ingestion. Run it before blaming our code for missing traces.
14. **neatlogs CLI and MCP server:** read traces from a terminal or from Antigravity (traces list, traces get, spans list). A fallback when the MCP link does not work.

What neatlogs cannot fix: expired keys, deprecated model ids, CAPTCHAs, site terms, Entire capture problems, Telegram delivery, human mistakes. neatlogs shows the symptom and the evidence. The fix is code or configuration.

## 2. Detection rules to create on Saturday (about 30 minutes)

Create these in the dashboard after the first real trace exists. Scope each to the relevant span names if the rule editor allows it. Tune thresholds after run B using our real averages.

Condition rules (numeric or boolean attributes):
1. D1 high cost: cost per run above 3 times our run B average.
2. D2 slow LLM call: latency above 20000 milliseconds on any LLM span.
3. D3 context bloat: total tokens above 8000 on a single LLM span.
4. D4 retry storm: attribute `attempt` greater than 2.
5. D5 fallback used: attribute `fallback_used` equals true.
6. D6 guardrail blocked: `neatlogs.guardrail.passed` equals false.
7. D7 unsupported in final: attribute `claims_unsupported` greater than 0 on the final verification round.
8. D8 loop suspicion: tool call count above 10 in one application.

Regex rules (text in span input or output):
9. D9 overreach words in Tailor output: `president|founder|director|years of experience|award winning|led a team of` (tune after seeing real output, these flag possible title or duration upgrades for review).
10. D10 provider errors in any response: `429|RESOURCE_EXHAUSTED|no longer available|NOT_FOUND|safety|blocked|I cannot`.
11. D11 prompt injection in fetched pages (Researcher input): `ignore previous|disregard|system prompt|you are now|do not tell the user`.
12. D12 portal blockers in portal responses: `captcha|login|sign in|forbidden|503|500`.

Classifier rules (meaning):
13. D13 sensitive leak: output mentions health, religion, disability or family income, scoped to Tailor and Edge Finder spans.
14. D14 generic essay: essay text that has no specific evidence from the applicant.

PII detection:
15. D15 PII flow: enable it and watch where personal data travels. With the synthetic persona hits are expected and harmless. For real users it shows exposure, and it helps check that no third party personal details (for example a professor's contact details) reach our prompts.

## 3. The failure catalog

Format: what it is, how to spot it in neatlogs, the fix, the prevention.

### 3.1 Setup and environment

1. **Model id deprecated or blocked for new keys** (Gemini 2.5 Flash returns 404 "no longer available to new users"). Spot: D10 fires, LLM span error with 404 and the model name in span detail. Fix: list the models your key can use, set `LLM_PRIMARY_MODEL` to a current one. Prevent: model id only from environment, a startup check that makes one tiny call and fails loudly.
2. **New style API key rejected** by the OpenAI compatible endpoint or raw calls. Spot: auth error text in the LLM span. Fix: try the Google GenAI SDK client for the primary model, still wrapped by neatlogs. Prevent: the B02 smoke test.
3. **No traces appear.** Spot: empty dashboard. Fix: run SDK Doctor local, then the probe, check the key and region (EU needs the EU endpoint), check init runs once at startup. Prevent: B02 acceptance includes a visible trace.
4. **Conflicting init error.** Calling init a second time with different configuration raises an error until shutdown. Fix: init only in `tracing.py`, one process per evidence run with its own tags. Prevent: no init calls anywhere else (rule in `AGENTS.md`).
5. **Python version unsupported** (needs 3.10 or newer and below 3.14). Spot: install fails. Fix: use 3.11 or 3.12 in the virtual environment.
6. **Spans missing from the background thread.** Spot: the run thread produces no children under the WORKFLOW. Fix: create the WORKFLOW span inside the thread. Prevent: test it in the first trace.
7. **Short scripts lose the last spans.** Fix: flush and shutdown at the end of `run_pipeline.py`.
8. **Each call shows as its own trace.** Fix: decorate the entry point as WORKFLOW so everything nests.
9. **Double counted spans** (wrap plus instrumentations on the same client). Fix: use wrap only.
10. **Cost or model name wrong for Gemini through the OpenAI client.** Spot: Analytics cost looks zero or the model name is odd. Fix: compute cost from tokens ourselves and record it as an attribute, or switch the SDK (NEATLOGS.md section 7).
11. **Secrets in traces or the public repo.** Spot: D15 or a search of span inputs for key patterns. Fix: rotate the key, use masking options on spans that handle secrets. Prevent: keys only in `.env`, never in prompts.

### 3.2 LLM calls

12. **Rate limit (429) or quota exhausted on the free tier.** Spot: D10, D4, D5, attempt attributes, the failed call and the fallback call as siblings. Fix: backoff then fallback model (already designed). Prevent: batch claims in the Verifier, cache dossiers, do the evidence runs before recording, keep a backup recording.
13. **Timeout or provider 5xx.** Spot: D2, error spans. Fix: retry then fallback. Prevent: sensible timeouts per call (30 seconds).
14. **Malformed JSON, markdown fences, extra text, truncated output.** Spot: parse errors, `json_repair` attribute, a response that ends mid object. Fix: repair prompt, then lower temperature regeneration, strip fences in code. Prevent: Pydantic schemas, higher max output tokens for the Tailor.
15. **Schema valid but wrong values** (ids that do not exist, scores outside 0 to 100). Spot: Edge Finder or Matcher span output with unknown ids. Fix: validate ids against the facts in code and drop bad ones. Prevent: the id validation step (already in the design).
16. **Safety filter blocks or the model refuses** (essays about hardship, health, family). Spot: D10 (`blocked`, `safety`, `I cannot`). Fix: rephrase the prompt to state the task is a personal statement the applicant wrote about themselves, fall back to the second provider, and mark the section `flagged` if both refuse. Prevent: keep sensitive facts out of prompts anyway.
17. **Context too long** (full CV plus Vault plus dossier). Spot: D3, token breakdown in span detail. Fix: send only the facts referenced by edges plus the core CV facts (already in the Tailor design). Prevent: a token budget per prompt that logs a warning.
18. **Output varies between runs** (A versus B noise). Spot: Analytics shows spread across the tagged runs. Fix: temperature 0.2 for extraction and judging, run each mode at least twice, report both.
19. **Prompt regression after an edit.** Spot: new prompt version has more D7 or D14 hits, or fewer thumbs up. Fix: revert the prompt version. Prevent: prompt id and version on every span, evaluation script (N09).
20. **Cost blowup from retry or verifier loops.** Spot: D1, Analytics cost per agent. Fix: cap rounds at 2 and attempts at 3, batch claims. Prevent: a per run budget that aborts and flags.
21. **Wrong model after fallback changes quality.** Spot: `model` attribute differs and outputs get worse, votes drop. Fix: re run the Verifier on fallback output, log the model on the application record.

### 3.3 Intake and data

22. **PDF text extraction garbage** (scanned CV, columns, odd encoding). Spot: Intake LLM span input is gibberish. Fix: paste text fallback in the UI, warn the user. Prevent: show an extraction preview on Screen 1.
23. **Facts altered during extraction** (numbers rounded, titles upgraded). Spot: compare span input and output, vote thumbs down. Fix: tighten the Intake prompt (keep exact wording), add a deterministic check that numbers in a fact appear in the source text. Prevent: that check.
24. **Facts split badly or duplicated.** Spot: the facts list has near duplicates. Fix: dedupe by normalized text in code.
25. **Sensitive fact not flagged, or non sensitive fact flagged.** Spot: D13 fires on output, or edges miss obvious evidence. Fix: category rules in `sensitive.py` plus unit tests. Prevent: the persona includes one sensitive fact that must never appear (trap 4).
26. **Empty or thin Vault.** Spot: Edge Finder returns no edges or only weak ones. Fix: gap questions, and a visible "add more detail" message in the UI.

### 3.4 Matching and listings

27. **GPA scale mismatch** (4.3 out of 5 compared with a 4.0 scale). Spot: wrong hard rule result in the Matcher TOOL span. Fix: normalize by scale in code with unit tests.
28. **Nationality or country rule wrong.** Spot: eligible listing skipped or ineligible matched. Fix: fix the listing data and the rule, add a test.
29. **Deadline passed or date parse error.** Spot: Scout drops everything, or dates fail to parse. Fix: strict `YYYY/MM/DD` parsing, and `deadline_note` for next cycle dates.
30. **Fit scores all similar or inflated.** Spot: Analytics shows scores clustered near the top. Fix: prompt asks to penalize missing evidence, add a calibration example.
31. **Stale or wrong listing data** (hand copied). Spot: a human check against the official page. Fix: re copy and record `copied_on`. Prevent: source URL and date on every listing.

### 3.5 Research

32. **Source unreachable, Crustdata 401, 429 or credits exhausted.** Spot: failed `crustdata_search` TOOL spans and `credits_used` attributes. Fix: cached dossier fallback and a `recovery_decision` span. Prevent: cache first, live only for top 2, log credits.
33. **Snippet not found in the fetched text** (the model invented a snippet). Spot: the code check drops facts, a drop count attribute. Fix: keep the check mandatory, drop the fact. Prevent: the rule that no snippet means no fact.
34. **Prompt injection inside a fetched web page** ("ignore previous instructions"). Spot: D11. Fix: treat page text strictly as data, never as instructions, strip it before the prompt, quote it inside delimiters, never let page text change tool choices. Prevent: a unit test with a malicious page.
35. **Outdated or irrelevant research** (old programme page, wrong professor). Spot: dossier facts with old retrieved dates or topics that do not match. Fix: show retrieved dates, expire the cache after 14 days. Prevent: the Edge Finder only uses facts that match a real applicant fact.
36. **Personal data about third parties** (professor emails, social profiles). Spot: D15. Fix: filter to role, research areas and publications only.

### 3.6 Edge Finder and Tailor

37. **Stretch edges** (a weak link presented as strong). Spot: low strength edges selected, Challenger overturns, thumbs down on the reason. Fix: threshold at 0.6 and the Challenger pass.
38. **No edges found.** Spot: empty edges list. Fix: gap questions and a generic but honest application, never padding.
39. **Invented claims in the Tailor output** (title upgrades, inflated duration, invented outcomes). Spot: D9, D7, GUARDRAIL blocked in run A. Fix: the Verifier enforcement and the Challenger. This is our run A to run B story.
40. **Segments without source ids.** Spot: the report counts segments with empty `source_ids`. Fix: reject such segments in code before verification.
41. **Essay over the word limit.** Spot: a word count attribute above the limit. Fix: send back with the limit, never truncate silently.
42. **Copying dossier text verbatim or sounding generic.** Spot: D14, thumbs down, Evals score. Fix: prompt asks for one specific reference in the applicant's own voice.
43. **Wrong voice or tone.** Spot: reviewer comments. Fix: voice rules in the prompt, keep first person.
44. **AI policy conflict** (restricted listing). Spot: a listing with `ai_policy` restricted that produced essay prose. Fix: Info and Draft Pack mode (see `PRODUCTION_UPGRADE.md` section 9).

### 3.7 Verifier

45. **Too strict** (removes good claims, leaves a thin essay). Spot: high `claims_removed` with many thumbs up on removed text. Fix: loosen the judge rules and use partial verdicts, review the deterministic number matching.
46. **Too loose** (misses an upgrade). Spot: D9 fires on a final output the Verifier passed. Fix: add the case to the judge prompt and as a regression test (persona trap).
47. **Number formats the regex misses** ("two hundred hours" versus 200). Fix: normalize numbers in the deterministic check.
48. **Judge inconsistent between calls.** Spot: same claim, different verdicts across runs. Fix: temperature 0.2, batch size limit, run twice for borderline claims.
49. **Loop does not converge in 2 rounds.** Spot: `unsupported_final` above 0 before removal. Fix: remove and flag after round 2 (already designed).
50. **Challenger over removes.** Spot: many overturned claims that look fine. Fix: require it to name the specific overreach, otherwise defend.
51. **Verifier cost heavy.** Spot: Analytics cost per agent. Fix: batch claims, use the cheaper model for extraction, the stronger one only for judging.

### 3.8 Applier and notifications

52. **Channel misclassified.** Spot: the Applier TOOL span shows the wrong channel. Fix: channel comes from the listing field, not from guessing.
53. **Portal 500, form validation error, field mismatch.** Spot: D12, failed `portal_submit` spans. Fix: retry 3 times then email or prepared fallback, map fields from the listing schema.
54. **CAPTCHA or login wall.** Spot: `blocker_check` span result, D12. Fix: stop, hand off, resume after Done. Never retry against a blocker.
55. **SMTP auth failure, attachment too large, bounce.** Spot: failed `send_email` span. Fix: app password check at startup, size check before sending, status stays `submitting`, fall back to prepared.
56. **Confirmation not read, status stuck at submitting.** Spot: the confirmation read TOOL span returns empty. Fix: poll the submissions endpoint a few times, then mark `unconfirmed` and tell the user. Never mark submitted without a confirmation.
57. **Double submission** (retry after a timeout that actually succeeded). Spot: two `portal_submit` spans with success. Fix: idempotency key per application, check the submissions endpoint before retrying.
58. **Done pressed before the user submitted.** Spot: confirmation check fails. Fix: friendly retry message, status stays `awaiting_user`.
59. **Telegram not delivered, wrong chat id, wrong link base URL.** Spot: failed `send_telegram` span, the notifications table `sent` false. Fix: retry unsent at the end of the run, `FRONTEND_BASE_URL` in config, a startup test message.
60. **Done button callback missed.** Spot: no callback span after the handoff. Fix: the polling thread health check, and the Done button in the app as a second route.

### 3.9 Coordinator and state

61. **Crash mid run.** Spot: a trace that stops mid tree. Fix: resume from persisted status (designed).
62. **Resume repeats paid calls.** Spot: duplicate LLM spans after resume, cost jump. Fix: idempotency checks before each step.
63. **Thread dies silently.** Spot: run stuck at running with no new spans. Fix: top level try and except in the thread that writes `failed` and an event, plus a heartbeat event.
64. **SQLite database locked** (two threads writing). Spot: error text in `sqlite_write` spans. Fix: one connection per thread, a write timeout, short transactions.
65. **One application failure stops the run.** Spot: later applications never start. Fix: catch per application (rule in `AGENTS.md`).
66. **Infinite retry loop.** Spot: D4 and D8. Fix: hard caps on attempts and rounds.
67. **Wrong status transition or event order.** Spot: the timeline shows impossible order. Fix: a single `set_status` helper with allowed transitions and tests.

### 3.10 Frontend and contract

68. **Contract mismatch** (field missing or renamed). Spot: frontend errors, `/verify_contract` output. Fix: align types, `contract:` commit.
69. **Null fields crash a screen** at early stages. Fix: skeletons and null checks (design brief).
70. **Polling never stops or hammers the server.** Fix: stop at final status, 2 second interval.
71. **Long text overflows or breaks layout.** Fix: wrap and scroll containers, test with the longest essay.
72. **Mock data differs from real data.** Fix: generate mocks from real responses once the backend runs.

### 3.11 Demo day and operations

73. **Rate limit during recording.** Prevent: record the runtime section from a backup recording if needed and say so.
74. **Free tier daily cap hit before the evidence runs.** Prevent: run A and B early Sunday, spend carefully on tests, use the fallback provider.
75. **Wifi or API outage in Ile Ife.** Prevent: record the backup run early, keep cached dossiers, test mobile data as a hotspot.
76. **Dashboard shows traces late.** Prevent: flush at the end of runs, wait a minute before taking screenshots.
77. **Secrets visible on screen in the video.** Prevent: hide `.env`, key pages and password managers.
78. **Late submission.** Prevent: our own deadline of 6:00 PM, post earlier.
79. **Entire not capturing.** Not a neatlogs problem, see `ENTIRE.md` section 8.

### 3.12 Safety and trust

80. **Sensitive fact leaks into output.** Spot: D13. Fix: the filter runs before any LLM call, plus a final output scan for sensitive terms. Treat as a release blocker.
81. **Invented content reaches a real application.** Spot: D7, D9. Fix: the Verifier is mandatory (production gate).
82. **Real personal data in public traces or the repo.** Prevent: synthetic persona only in the public repo and in screenshots, masking on spans for real users.
83. **Temptation to bypass a CAPTCHA to save a demo.** Rule: never. The handoff is the feature.

## 4. A 10 minute triage routine (run after every evidence or test run)

1. Open the traces list filtered by the run tag. Scan detection badges first.
2. Open Analytics for cost and latency by agent and tool. Note the top cost and the slowest tool.
3. Open the slowest or most expensive trace and read the timeline for idle gaps and retry stacks.
4. Open any trace with D6, D7, D9 or D13 badges, read the span detail, and vote thumbs down on bad outputs.
5. Ask Investigate one question (section 5).
6. Leave a comment on the span with the finding, tag the teammate who owns the fix.
7. Add the finding to `docs/evidence/improvement_log.md` (trace link, cause, fix, commit hash).
8. Make the fix through Antigravity, using the neatlogs MCP or the CLI to read the trace.

## 5. Investigate prompts library

Use Fast mode for simple questions and Pro mode for broad ones.

1. "Start an investigation on the last 20 traces tagged run_A and tell me the most common cause of unsupported claims."
2. "Which agent spends the most tokens, and which prompt in it is the longest?"
3. "Find traces where fallback_used is true and compare the output quality to non fallback runs."
4. "Show runs where the portal submit failed, and what the agent did next."
5. "Find traces where the Verifier passed but the output contains words like president or years of experience."
6. "Why are there so many D10 detections today?"
7. "List the slowest 5 spans and what they were waiting on."
8. "Did any prompt contain sensitive terms such as health or religion?"
9. "Which Researcher inputs contained instruction like text from a web page?"
10. "Summarize what changed between run B and run C and whether it is a real improvement."

## 6. Failures to inject on purpose (demo and evidence)

Already designed: `llm_429`, `bad_json`, `portal_500`, `captcha_wall`.
Add if time allows (each is cheap and makes a strong trace):
1. `research_down`: the Crustdata call fails, the cached dossier is used, a `recovery_decision` span explains why.
2. `smtp_fail`: the email send fails, the Applier falls back to a prepared package and a Telegram alert.
3. `injection_page`: a demo about page contains an instruction like text, D11 fires, the agent treats it as data and ignores it. This is also a security story judges like.
4. `overreach_prompt` (test only): a Tailor prompt variant that tends to upgrade titles, used to show the Verifier and Challenger catching it. Label it as a test.

All injected failures carry the `failure_injected` attribute and stay labeled in the evidence.

## 7. Evidence from this playbook

1. [ ] Screenshot of the detections list (D1 to D15 created).
2. [ ] Traces list showing detection badges on real runs.
3. [ ] One Investigate thread with its linked evidence.
4. [ ] Analytics views for cost by agent and tool errors.
5. [ ] Thumbs up and down votes on a set of Tailor outputs, and the filtered view.
6. [ ] A comment thread between Memeshi and Ayo on a span.
7. [ ] The triage routine applied once, written into `docs/evidence/improvement_log.md`.
