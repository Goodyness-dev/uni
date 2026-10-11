# 18_DEMO_SCRIPT.md

The demo video script, 3 minutes maximum (aim for 2:50). Replace braces like {N_A} with real values from `17_EVIDENCE_CHECKLIST.md`. Say a number only if it is in the evidence file.

Rules:
1. Judges score each tool on five aspects: architecture, implementation, runtime, reasoning, result. The script marks where each is covered.
2. neatlogs is on screen within the first 20 seconds.
3. The persona is fictional and mock listings are labeled DEMO LISTING.
4. Never show secrets. Hide `.env`, key pages and password managers.

## 1. Setup before recording

1. Two people: one narrates, one drives (or record narration separately over the screen recording).
2. Screen 1920 by 1080, browser zoom 110 percent, bookmarks bar hidden, notifications silenced.
3. Tabs ready in this order: the app at `localhost:3000`, neatlogs (traces list filtered by the evidence tags, plus the run A and run B traces and a recovery trace), the Antigravity CLI session where it read a trace (screenshot is fine), GitHub with the `entire/checkpoints/v1` branch, the entire.io checkpoint view, the cfo.ai Page, and a phone with Telegram open (screen mirror or a pre recorded clip).
4. Database seeded to the known state from B25. All failure flags OFF except `captcha_wall` ON only for the handoff segment.
5. Backup recording of the whole runtime section exists.
6. Free tier limits: do one dry run earlier, not right before recording.

## 2. Script with timestamps

**0:00 to 0:08, hook**
Screen: the app home with the demo persona loaded.
Say: "ScholarPilot is an agent that finds scholarships you qualify for, researches the school, picks your real evidence, verifies every claim, then applies or hands off."

**0:08 to 0:20, neatlogs first (obvious from the start)**
Screen: the neatlogs span tree of one full run, with a caption "Every step traced in neatlogs" and the GUARDRAIL span showing Passed.
Say: "Every agent step, model call and tool call is a neatlogs span. The verifier is a guardrail, so the dashboard shows Passed or Blocked."

**0:20 to 0:35, architecture**
Screen: one slide of the flow: Intake, Scout, Matcher, Researcher, Edge Finder, Tailor, Verifier, Challenger, Applier, Coordinator with SQLite.
Say: "A plain Python coordinator keeps state in SQLite and runs the agents. Claims are grounded in three sources: the CV, a personal profile vault, and a sourced research dossier."

**0:35 to 1:05, runtime**
Screen: press Run agent. Matches appear with fit scores while the activity feed scrolls. Open the top application: dossier sources with links, Evidence used cards, source pills on the essay, the green All claims verified banner, an overturned claim. Telegram buzzes on the phone.
Say: "It found five scholarships, matched three, researched the top ones, and chose evidence automatically. Here it used {fact}, because the programme values {value}. Every sentence has its source. Nothing is invented."

**1:05 to 1:45, neatlogs: reasoning and result**
Screen: run A trace with the Blocked guardrail, then Antigravity reading that trace through the neatlogs MCP server, then the Entire checkpoint of the fix, then run B and the comparison table, then one recovery decision span.
Say: "In run A the writer produced {N_A} claims the sources do not support, like turning assistant coordinator into president. Antigravity read that trace through the neatlogs MCP server and proposed the fix. In run B the same task has {N_B}, at {X} percent more cost. A second loop cut cost by {Y} percent. And every recovery is a decision span with its reason: rate limited twice, so it switched to the backup model."

**1:45 to 2:10, recovery and submission**
Screen: the portal throws a CAPTCHA, the app shows Needs you, Telegram handoff arrives, solve the fake challenge, tap Done, confirmation code appears. Two second cut to the recovery trace.
Say: "We never bypass CAPTCHAs. The agent detects the blocker, stops, prepares everything, asks me for ten seconds, then resumes and only marks submitted after it sees the confirmation code."

**2:10 to 2:30, Entire (architecture, implementation, runtime, reasoning, result)**
Screen: GitHub with the checkpoints branch, a checkpoint open (Sessions and Changes tabs) for the Verifier commit, then the entire graph impact or diff output.
Say: "Entire saved the context behind every AI made change on its own branch. This checkpoint shows why we made the verifier a two round loop. The graph mapped what the change touched, which made reviewing AI written code faster."

**2:30 to 2:52, cfo.ai (architecture, implementation, runtime, reasoning, result)**
Screen: the cfo.ai Page: pricing tiers, cost per application, the three scenarios, runway. Change a price and watch margin and runway update.
Say: "We gave cfo.ai the real cost per application from our neatlogs traces, {C} dollars. At {P} dollars per application the margin is {M} percent and runway in the base case is {R} months. Costs are measured, prices and growth are assumptions."

**2:52 to 3:00, close**
Screen: repo URL and team names.
Say: "ScholarPilot. Personal, verified, honest. Repo link below."

## 3. If you run over time

1. Cut the architecture slide first, then shorten the runtime section.
2. Never cut the three tool segments, the Blocked to Passed story, or the CAPTCHA handoff.
3. Check the exported file length, not the timeline.

## 4. If something breaks while recording

1. Rate limit: use the backup recording for the runtime section only and say "recorded earlier".
2. CAPTCHA flow fails: re run once. If it fails again, show the recorded handoff clip.
3. neatlogs dashboard slow: use the screenshots from `docs/evidence/screenshots/` and say they are from the evidence runs.

## 5. Pre record checklist

1. [ ] Phone notifications on and Telegram open.
2. [ ] Failure flags off except the planned one.
3. [ ] neatlogs filtered to evidence runs, with a recovery trace and the run A and B traces open in tabs.
4. [ ] Antigravity MCP session screenshot ready (or the manual reading shown honestly).
5. [ ] Entire checkpoint view and graph output ready.
6. [ ] cfo.ai Page open and the price change rehearsed.
7. [ ] No secrets visible. Bookmarks hidden.
8. [ ] Exported video is 3:00 or less, audio clear, text readable at 1080p.
9. [ ] Backup recording saved.
