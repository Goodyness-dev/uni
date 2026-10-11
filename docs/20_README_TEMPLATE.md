# 20_README_TEMPLATE.md

Copy the block below into the repo root `README.md` on Monday morning (a short stub is fine from Saturday). Fill the braces with real values. Judges read this file, so keep it honest and make the three sponsor tools obvious.

````
# ScholarPilot

An agent that finds scholarships you qualify for, researches the school, picks your real evidence, verifies every claim, then applies or hands off.

Built in 48 hours for the neatHack AI agent hackathon (October 10 to 12, 2026) by {team name}: Memeshi (agents and backend) and Ayo (design and frontend). All code in this repository was written during the hackathon (see the commit history).

Demo video: {video link}
Business plan (cfo.ai, read only): {cfo.ai page link}

## What it does

1. You give it your CV, transcript, preferences and a personal Profile Vault (sports, volunteering, certifications, leadership, hardships, goals).
2. It matches you to scholarships using hard eligibility rules and a fit score.
3. For the best matches it researches the school and programme (every fact has a source link and a snippet checked in code).
4. It finds your strongest real evidence for each scholarship automatically.
5. It writes a tailored CV summary, CV bullets and an essay answer. Every sentence cites the facts it came from.
6. It verifies every claim against the sources, then tries to disprove its own claims. Unsupported claims are removed and listed.
7. It submits where it safely can (our demo portal and email), hands off to you when a CAPTCHA blocks it, and prepares a ready package for real scholarships. You get a Telegram message at each step.

Rules we built in: it never invents experience, never bypasses a CAPTCHA, never submits to a real scholarship site, and never uses sensitive details unless a scholarship requires them and you agreed.

## How we use the three required tools

### neatlogs (traces, guardrails, the improvement loop)
1. Every agent step, model call and tool call is a span. The verifier is a GUARDRAIL span that shows Passed or Blocked.
2. Run A (before) and run B (after) are tagged and compared: unsupported claims {N_A} to {N_B}, cost {cost_A} to {cost_B}.
3. Our coding agent read the run A trace through the neatlogs MCP server and proposed the fix. See `docs/evidence/improvement_log.md`.
4. Every recovery (retry, fallback, handoff) is a decision span with its reason.
5. 15 detections watch for overreach words, cost spikes, prompt injection and sensitive leaks.
6. Screenshots: {span tree}, {guardrail blocked and passed}, {A versus B}, {detections}, {recovery decision}.

### Entire (checkpoints)
1. Entire was enabled before the first commit on both machines. Code was written through the Antigravity CLI.
2. Checkpoints are on the `entire/checkpoints/v1` branch: {branch link}.
3. A checkpoint for the verifier change: {screenshot}. entire graph output: {file}.

### cfo.ai (business plan)
1. Cost per application ${C} comes from our neatlogs traces.
2. Pricing tiers, three scenarios and runway: {cfo.ai page link}. Summary in `docs/evidence/business_plan.md`.
3. Costs are measured, prices and growth are assumptions.

Optional data source: Crustdata for live research (if used: describe how).

## Architecture

{Insert the flow picture or this list}
Intake, Scout, Matcher, Researcher, Edge Finder, Tailor, Verifier (audit, enforce, challenger), Applier, Packager and a Coordinator that keeps state in SQLite, retries, recovers and notifies.

Stack: Python (FastAPI, SQLite, Pydantic), Next.js, Gemini through an OpenAI compatible client with a second provider as fallback, Telegram Bot API, Gmail SMTP.

## Run it

Backend (from `backend/`):
1. Create a virtual environment named `.venv` and activate it.
2. `pip install fastapi uvicorn pydantic openai neatlogs httpx pypdf reportlab jinja2 pytest`
3. Copy `.env.example` to `.env` and fill the values.
4. `python run_server.py`

Frontend (from `frontend/`):
1. `npm install`
2. Create `.env.local` with `NEXT_PUBLIC_API_BASE=http://localhost:8000` and `NEXT_PUBLIC_USE_MOCKS=false`
3. `npm run dev` and open http://localhost:3000

Click Load demo persona, then Run agent.

Tests: from `backend/` run `pytest`.

## Evidence

See `EVIDENCE.md` and `docs/evidence/`: run A and B metrics, recovery runs, improvement log, screenshots, business plan.

## Honest limitations

1. Real scholarship portals are never automated. Real listings end as prepared packages.
2. The demo school pages and three of the five listings are fictional and labeled DEMO.
3. The persona is fictional. No real personal data is in this repository.
4. Verification reduces invented claims but cannot guarantee a perfect application. Users must review everything before submitting.
5. Free tier rate limits shaped our testing. {anything else}

## Team

Memeshi: agents, backend, tracing, evidence. Ayo: design, frontend, demo portal pages.
````

## Notes for filling it

1. Do not paste numbers you do not have. Delete the sentence instead.
2. Add the screenshots under `docs/evidence/screenshots/` and link them.
3. Check every link from a logged out browser.
4. Keep the sponsor sections near the top, judges look for them.
