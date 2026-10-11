# TOOLS_RESEARCH.md

> Pack v2 note: reference only. The working instructions are in `03_TOOLS_SETUP.md` and `09_NEATLOGS_SPEC.md`. Older file names mentioned here map to the v2 files.


Research on neatlogs, Entire, cfo.ai and Crustdata, and exactly how ScholarPilot should use each one. Researched on Saturday October 10, 2026 from the official docs, the PyPI page, the GitHub repos and the neatHack page.

How to read this file: facts below come from those sources. Anything marked VERIFY could not be confirmed and must be tested in the first hour. Exact command lines that contain dashes are not copied here. Copy them from the named doc page instead, so nothing is mistyped.

## 0. Hackathon facts confirmed on the neatHack page

1. Teams are 1 to 4 people. EVERY member must register on Luma using the SAME team name, and each person can join only one team. Check that all 4 of your people registered with one identical team name.
2. Submission is ONE public quote post of the official neatlogs submission post on X. Use the Submit on X button (it appears during the submission window), fill team, name, project, public repo and demo link, keep the official post attached, then publish. Opening the draft alone does not submit.
3. The video must explicitly cover neatlogs, Entire and cfo.ai, and for EACH tool: architecture, implementation, runtime, reasoning and result.
4. Judges must be able to verify that commits were made during the hackathon.
5. Use neatlogs and Entire to BUILD and IMPROVE the agent, and use cfo.ai to PLAN its business. Crustdata is an optional data source (credits for everyone participating), not a required tool.

## 1. neatlogs

### 1.1 What it is

Observability for AI agents: every run traced, every failure caught, every fix tracked. A trace is one run of the app, a span is one step inside it (an LLM call, a tool call). The dashboard has Traces, Session Replay, Comments, Detections, Investigate (AI search), Tools and MCPs, Analytics, Fixes and Experiments.

### 1.2 Install and setup facts

1. Install the `neatlogs` package from PyPI. It needs Python 3.10 or newer and BELOW 3.14. Use Python 3.11 or 3.12 for the project.
2. Extras exist for libraries, for example the OpenAI extra and the Google GenAI extra. Install the extra for each LLM SDK we use.
3. The quickest setup is the setup wizard (run through npx from the neatlogs docs page "Instrument with the Wizard"). It detects the stack and instruments code. We can still write the instrumentation ourselves, but the wizard is worth trying on the first trace.
4. An official Agent Skill exists in the neatlogs skills repo on GitHub. The exact install line is on the PyPI page for neatlogs. It has an agent option, so check whether Antigravity is accepted. If not, install it for any agent and copy the skill folder into the Antigravity skills folder.
5. Project API key comes from the dashboard. Keep it in `NEATLOGS_API_KEY`. EU projects need the EU endpoint option in init.
6. A "doctor" check exists: run the neatlogs module with the doctor option and the local flag from the project root to check the install without network. A second run with the probe flag proves traces reach the dashboard. Use it after B02. Exact flags are on the Python SDK page.

### 1.3 Core API (confirmed from the Python SDK page)

1. `neatlogs.init(...)` is called ONCE. Main parameters: `api_key`, `endpoint`, `workflow_name`, `instrumentations`, `tags` (list of strings attached to every trace from that process), `user_id`, `capture_logs`, `sample_rate`, `mask`, `pii_enabled`, `debug`.
2. `neatlogs.wrap(client)` wraps an LLM client so every call is traced as an LLM span with prompt, response, tokens, latency and model. It works for OpenAI, Anthropic, Google GenAI, Azure OpenAI, Bedrock, Vertex AI, OpenRouter and several agent frameworks.
3. `@neatlogs.span(kind=..., name=...)` wraps your own function. It captures arguments as input and the return value as output. Works for sync and async. Other parameters: `role` and `goal` for AGENT, `tool_name`, `parameters` and `description` for TOOL, `capture_input`, `capture_output`, `mask`.
4. `with neatlogs.trace(name, kind=...) as span:` opens an inline span and lets you set attributes with `span.set_attribute(...)`.
5. `neatlogs.log("message with {placeholders}", level=..., key=value)` writes a structured log line inside the active span (needs `capture_logs` on in init).
6. `neatlogs.flush()` and `neatlogs.shutdown()`: always at the end of scripts. In a FastAPI server call them once at shutdown, in the lifespan handler. Do not flush per request.
7. Python rule: if you use `instrumentations=[...]`, call init BEFORE importing that library. `neatlogs.wrap()` has no such rule.
8. Each call without a surrounding span becomes its own trace. So decorate the entry point with a WORKFLOW span so everything nests under one root.

### 1.4 Span kinds (this corrects our earlier files)

The `@span` decorator accepts EXACTLY these uppercase kinds: WORKFLOW, AGENT, CHAIN, TOOL, RETRIEVER, EMBEDDING, GUARDRAIL, MCP_TOOL. Any other value raises an error. LLM spans come from `wrap()`. RERANKER and VECTOR_STORE come from `trace()`.

Our earlier files said lowercase agent, llm and tool. That is wrong. Use the uppercase kinds.

### 1.5 Custom attributes (important for the Verifier)

A GUARDRAIL span has special attributes: `neatlogs.guardrail.input` (content checked), `neatlogs.guardrail.passed` (true or false, shown in the dashboard as Passed or Blocked) and `neatlogs.guardrail.output` (reason). TOOL spans use `neatlogs.tool.name`, `neatlogs.tool.description`. RETRIEVER spans use `neatlogs.retriever.query`, `neatlogs.retriever.top_k` and indexed documents.

### 1.6 Prompt templates and managed prompts

1. `SystemPromptTemplate` and `UserPromptTemplate` capture the template and the runtime variables for an LLM call, linked to its span, when passed to `trace(kind="LLM", ...)`.
2. Experiments has Prompts (version controlled prompts with labels such as production, fetched at runtime by label), a Playground (needs your own provider keys under Settings) and Datasets (marked coming soon).

### 1.7 Detections, Fixes and the MCP server (the improvement loop)

1. Detections flag problems in traces. Fixes proposes a root cause and a code fix for failing traces.
2. Dispatching a fix to a cloud coding agent currently supports Cursor Cloud Agents only and needs a connected GitHub repo. It does not support Antigravity. Do not plan around dispatch.
3. The neatlogs MCP server lets a coding agent read traces directly. Endpoint: the ingest host plus the MCP path, authenticated with your project key as a bearer token, using streamable HTTP. The wizard can add it to Claude Code or Cursor automatically, so for Antigravity add the same entry by hand to its MCP settings (VERIFY the Antigravity config location).
4. MCP tools: search traces, get full trace context (metrics, span tree with inputs and outputs, code locations, detections), list detections, detection trend, list and read fix suggestions and their investigations, accept or dismiss fixes, and push a trace from the coding agent.

### 1.8 How ScholarPilot uses neatlogs

Mapping of our design to neatlogs concepts:

1. Coordinator run: one WORKFLOW span named `scholarpilot_run`. Each application is a child AGENT or CHAIN subtree.
2. Intake, Matcher, Researcher, Edge Finder, Tailor, Applier: AGENT spans (set `role` and `goal`).
3. Scout reading the listings file and the dossier cache: RETRIEVER spans with the query and returned listing ids.
4. Verifier: a GUARDRAIL span per round with `passed` true or false and the reason. This makes the dashboard show Passed or Blocked, which is perfect for the demo.
5. Deterministic claim check, blocker check, SMTP send, portal submit, Telegram send, SQLite writes, Crustdata calls: TOOL spans with `tool_name`.
6. Every LLM call: through `neatlogs.wrap(client)`, plus a `trace(kind="LLM")` with prompt templates so prompt versions are visible.
7. Fallback model: a second wrapped client. The trace then shows the failed primary call and the fallback call as siblings.
8. LLM SDK choice: neatlogs officially supports OpenAI and Google GenAI clients. Our plan uses the OpenAI SDK pointed at Gemini's compatible endpoint. TEST in task B02 that the trace shows the real Gemini model name, tokens and cost. If it does not, switch the primary client to the Google GenAI SDK (construct the client after init, as the docs require) and keep the OpenAI SDK only for the fallback.

Run A versus run B labeling (replaces the guess in NEATLOGS.md):

1. Tags are set in init and apply to every trace from that process. The evidence runs use the CLI script, one process per run, so pass `tags` such as `run_A` or `run_B` plus `evidence`. This gives a clean filter in the dashboard.
2. Also set the mode, prompt version and application id as span attributes so the A versus B difference is searchable inside a trace.
3. Use `workflow_name` for the product (`scholarpilot`), never for the run label. The docs say tags are for anything that varies between runs.
4. The Analytics page aggregates cost, latency, errors and tools. Use it for the comparison screenshot. VERIFY whether it can filter by tag for a side by side view. If not, screenshot each tagged filter and put the numbers in a table.

The improve loop to show the judges (this is the heart of the neatlogs and Entire score):

1. Run A produces a trace where the Verifier GUARDRAIL reports unsupported claims.
2. In Antigravity, with the neatlogs MCP connected, ask the agent to find that trace, read its context and propose a fix.
3. The agent changes the code. The commit creates an Entire checkpoint that records WHY.
4. Run B shows the same task with fewer unsupported claims. Compare in neatlogs.

Practical rules:

1. Long running server: init once at startup, flush and shutdown in the FastAPI lifespan handler.
2. Background threads: test that spans created inside the run thread appear. VERIFY in the first trace. If they are missing, create the WORKFLOW span inside the thread.
3. Privacy: use `capture_input=False` or the `mask` option on spans that handle full CV text for real users. For the synthetic persona full capture is fine and is better for the demo.
4. Do not enable PII redaction in a way that hides the evidence the judges need. Decide before the evidence runs.

## 2. Entire

### 2.1 What it is

Entire hooks into git and captures AI agent sessions (prompts, transcripts, tool activity, changed files, token usage). Sessions and checkpoints are stored on a separate branch named `entire/checkpoints/v1`, so normal history stays clean. A checkpoint is created whenever you or the agent make a git commit. Git hooks add an Entire checkpoint trailer to the commit message, and an attribution trailer showing the share of agent written lines. Multiple sessions can run on one commit and are preserved separately.

### 2.2 Antigravity support (this resolves our biggest worry)

1. Entire documents an Antigravity integration. It captures prompts, session transcripts, recorded file changes and token usage from the Antigravity CLI and links each session to its git commits.
2. IMPORTANT: the docs say Antigravity CLI. An older GitHub issue said sessions from the Antigravity IDE were not detected by the hooks. So write code through the Antigravity CLI, and use the IDE only for reading, previews or UI work that you do not rely on for evidence. VERIFY by making one test commit from each and checking which one creates a checkpoint.
3. Check support in your installed build with the Entire agent list command. If antigravity is not listed, update Entire.
4. Setup: authenticate the Antigravity CLI, install or update Entire, then either enable Entire in the repo with the agent option set to antigravity, or add the agent to an already enabled repo using the Entire agent add command. The Entire quickstart page shows the exact lines. Entire manages an `entire` entry in the file `.agents/hooks.json` and preserves other entries. When the `agy` command is on the PATH it also wraps the title command in the Antigravity CLI settings file to capture token usage.
5. Check capture with Entire status and Entire doctor. There is NO tracking banner inside Antigravity, so do not expect one.
6. Known limit: subagent sessions are not attached to the parent checkpoint. Antigravity subagents run as separate conversations. Keep important work in the main conversation so it is captured.
7. Entire creates `.entire/settings.json` (shared) and `.entire/settings.local.json` (personal). Commit the shared one. Entire can ask once whether to link commits to an active session and remember the answer, so choose "always" for the repo setting.

### 2.3 Other facts from the docs

1. Other supported agents: Claude Code, Codex, Copilot CLI, Cursor, Factory, OpenCode and Pi. You can enable several at once. If Antigravity capture fails for any reason, Cursor or Claude Code are fallbacks, but ask in the Discord first.
2. Install uses the official script from entire.io (a curl installer, plus Scoop on Windows and a Go install route). Copy the exact line from the Entire installation page. A stable and a nightly channel exist. Use stable.
3. Inspect checkpoints locally with the Entire checkpoint commands (explain, rewind and list), and sessions with the Entire session commands. Entire login authenticates the CLI with device auth.
4. On entire.io you open a repository, pick a branch, see commits grouped by day with their checkpoints, and open a checkpoint. The checkpoint header shows commit, branch, author, agent, files changed, AI percentage and token usage. The Sessions tab shows prompts, transcript and tool activity. The Changes tab shows the diff. This is the best demo screen.
5. By default session logs are pushed when you push. A config option controls auto push of the checkpoints branch, and a flag can skip pushing sessions. Make sure the checkpoints branch reaches GitHub, because the judges verify through the public repo.
6. Privacy: transcripts contain your prompts and the agent's tool output. Never paste API keys or real personal data into the agent, because it becomes part of the stored session on a PUBLIC branch.

### 2.4 entire graph

1. entire graph is a plugin for the Entire CLI that gives the coding agent a deterministic map of the codebase: functions, types, routes and call relationships. It runs locally and does not send code to a model or service.
2. Install it with the Go toolchain, so install Go first. Then register the plugin with the Entire plugin install command. The exact lines are on the Entire "Install and Enable entire graph" page.
3. Run the entire graph command that sets up agents (the first command in the Entire graph CLI reference) in the repo. It writes a graph agent guide file inside the `.entire` folder and adds MANAGED blocks to `AGENTS.md` and `CLAUDE.md`. Do this AFTER our own `AGENTS.md` is committed, review the diff, and keep our rules intact. The managed block tells the agent to query the graph before searching with grep.
4. Commands from the CLI reference: index, capabilities, impact, neighbors, def, explain, commit, diff, checkpoint (analyze the commit linked to a checkpoint), verify (runs a command you give it, with your privileges, so use it carefully), snapshot, symbols, edges, stats (compares graph use against grep and file reads in local transcripts with an estimated token saving), doctor and version.
5. Language coverage comes in two tiers. Run the capabilities command with its JSON output and read the semantic languages list to confirm Python and TypeScript are traced for relationships. Dynamic connections (reflection, generated code) can be missed.
6. The stats saving is a local heuristic, not a benchmark. If we quote a number in the demo, call it an estimate.

### 2.5 How ScholarPilot uses Entire

1. Enable before the first commit, on BOTH machines, with the Antigravity agent.
2. Smoke test at 8:15 AM: make a tiny change through the Antigravity CLI, commit, then check that Entire status is enabled and the checkpoint exists on the checkpoints branch.
3. All coding goes through the Antigravity CLI in the main conversation, one conversation per task ID, committed right after (the commit creates the checkpoint).
4. Put the reasoning in commit bodies. Entire stores the session, and judges read both.
5. Use entire graph for two things: (a) give the agent impact analysis before it touches `llm.py`, `coordinator.py` or the API contract, (b) generate demo evidence with the graph diff and impact commands for the Verifier change.
6. Evidence to capture: Entire status after setup, the entire.io branch view with checkpoints, one checkpoint open (Sessions and Changes tabs) for the Verifier change, the attribution percentage, the graph output, and the checkpoints branch visible on GitHub.

## 3. cfo.ai

### 3.1 What it is

cfo.ai (formerly Runway Financial, rebranded in 2026) sells Ari, an AI finance coworker. You ask a business question, Ari builds or updates a live financial Model behind the answer, and you can open the Model, inspect and change assumptions, and see results change. The calculation engine is built for agents. Work persists after the conversation.

### 3.2 Concepts from the docs

1. **Model**: the shared financial model, with Variables and Dimensions (see the Glossary).
2. **Scenarios**: test a change without changing the Main model, then compare outcomes. We use Base, Growth and Conservative.
3. **Pages and dashboards**: turn model data into tables, charts and written context. A Page can be shared as read only, you choose its Scenario, and you can add a password. This gives us a link for the submission.
4. **Connect data**: accounting, HR, CRM, spreadsheet, database or uploaded data. We have no revenue, so we skip connectors.
5. **Import a spreadsheet**: rebuild a workbook as a native Model. Option if we prepare our numbers in a sheet first.
6. **Automation**: teach Ari a repeatable workflow or schedule analysis.
7. **MCP and Slack and API** access exist, so Ari can be asked from a terminal. VERIFY the MCP setup on the docs site, and whether it works from the Antigravity CLI.
8. Pricing facts from one third party profile: the Startup plan was $295 per month as of September 2026, with a 14 day trial and extra AI credits sold separately. This is why the hackathon requires cancelling right after signup. The neatHack team provides credits directly, so confirm in Discord before spending anything.

### 3.3 How ScholarPilot uses cfo.ai

1. Sign up at the neatHack link, cancel the subscription immediately (screenshot the cancelled state), and confirm that credits arrived.
2. Prepare a one page assumptions file from `CFO_PLAN.md` with REAL costs from run B (tokens, cost per application, latency, fallback share, retry overhead, Crustdata credits per scholarship) and clearly labeled assumptions for prices and growth.
3. Ask Ari to build the Model from that file: revenue by tier, variable cost per application, fixed costs, cash and runway. Then ask for the three Scenarios and a pricing sensitivity (for example, what if the verifier needs 3 rounds, or LLM prices change by half).
4. Build a Page called "ScholarPilot business plan" with the pricing tiers, unit economics, scenarios chart and runway. Share it read only, and add the link to `EVIDENCE.md` and the X post. Take screenshots too, in case sharing is limited.
5. Show Ari's traceability: click from a number to its assumption. Judges score whether cfo.ai was used well to plan the business around the agent, so show the link from neatlogs cost data to the Model input.
6. Keep honesty: costs measured, prices and growth assumptions.
7. Optional wow: ask Ari the one pricing question that matters for us (for example, how many applications per user per season make the Season pass profitable at a Nigerian price point).

## 4. Crustdata

### 4.1 What it is

An API data layer for company and people data, plus web search and page fetch. Public docs cover Company, Person, Job, Web and Social Post APIs. The base URL is api.crustdata.com. Every request needs the API key and the API version header (a date in November 2025, shown in the docs). Company and Person live endpoints are plan specific and enterprise only. An MCP server also exists on the Crustdata site.

### 4.2 The APIs that matter to us

1. **Web Search** (live): one query across sources including web, news, scholar articles, scholar authors, AI overview and social. Cost: 1 credit per query. This is useful for professor research, because the scholar author and scholar article sources return research areas and publications.
2. **Web Fetch** (live): up to 10 URLs per request, returns page title and full HTML. Cost: 1 credit per page. Use it on URLs returned by search or on the listing's official page.
3. **Person Enrich**: takes a professional network profile URL and returns a profile (basic profile and social handles by default, experience on request). Certifications and honors need extra field permission on the key.
4. **Person Search**: find people by name, title, company or location. Then enrich.
5. **Company Identify and Enrich**: resolve a domain or name to a company and get a profile.
6. Rate limits apply per API key. Email the Crustdata team for higher limits.

### 4.3 What to use and what to skip

Use:
1. Web Search with scholar sources and news sources for the Researcher, on the top 2 scholarships only.
2. Web Fetch for official institution and programme pages.
3. Cache everything in `dossier_cache` so the demo never depends on live calls.

Skip or use with great care:
1. Do NOT use the human mode option on search or fetch. It attempts a browser like path past bot protection, which breaks our rule of never evading bot controls.
2. Person Enrich on professors: this is personal data about third parties. Use only public academic information (role, research areas, publications), never contact details or social media. Prefer Web Search with scholar sources over profile enrichment.
3. The sales oriented features (funding, headcount, hiring signals) do not help scholarships.

### 4.4 How ScholarPilot uses Crustdata

1. Researcher flow per scholarship: 1 search for the programme and its stated priorities, 1 to 2 scholar author or article searches for the programme lead or relevant professor, 1 news search for recent programme news, then up to 4 page fetches. Roughly 8 credits per scholarship.
2. The existing rule stays: every dossier fact needs a source URL and a snippet that really appears in the fetched text, checked in code. Crustdata only changes how we obtain the text.
3. Trace every call as a TOOL span and record credits used. This gives the real "research cost per scholarship" for `CFO_PLAN.md`.
4. Fallback: if a Crustdata call fails or credits run out, use the cached dossier. This is also a recovery case for the demo (research source unreachable).
5. Credits: the hackathon page says 5,000 credits for everyone participating, delivered after the hackathon begins. Confirm in the Discord how to claim them. Our budget is small (under 100 credits for 5 scholarships), so rate limits matter more than credits.
6. Time box: Crustdata is optional. If setup takes more than 45 minutes, keep the cached dossiers and mention Crustdata as the live research path.

## 5. How the four tools fit together in ScholarPilot

1. Build time: Antigravity CLI writes code, Entire captures each session and commit, entire graph gives the agent the code map.
2. Run time: the agent runs, neatlogs traces every step, Crustdata supplies research text, Telegram and the portal handle the outputs.
3. Improve loop: neatlogs MCP lets Antigravity read the failing trace, the fix is committed (Entire checkpoint records why), the next run is traced and compared.
4. Business plan: neatlogs cost data and Crustdata credit cost go into cfo.ai, which produces pricing, margins and runway.

## 6. Demo segments per tool (architecture, implementation, runtime, reasoning, result)

neatlogs (about 30 seconds):
1. Architecture: the span tree with WORKFLOW, AGENT, RETRIEVER, TOOL, GUARDRAIL and LLM spans.
2. Implementation: the wrap call and one span decorator in the code.
3. Runtime: a live trace with tokens, latency and cost.
4. Reasoning: why we added the Verifier, based on run A.
5. Result: run A versus run B numbers, and the recovery trace.

Entire (about 20 seconds):
1. Architecture: checkpoint branch next to main.
2. Implementation: Antigravity CLI hooks plus the commit trailer.
3. Runtime: checkpoints growing during the 48 hours.
4. Reasoning: open the Verifier checkpoint and read the context.
5. Result: attribution percentage, graph impact output.

cfo.ai (about 20 seconds):
1. Architecture: neatlogs cost data feeding the Model.
2. Implementation: the assumptions and Variables.
3. Runtime: change a price and watch margin and runway update.
4. Reasoning: why that lead pricing tier.
5. Result: margin, runway and the shared Page.

## 7. Corrections to earlier files (apply these)

1. `NEATLOGS.md` section 2: span kinds are uppercase (WORKFLOW, AGENT, CHAIN, TOOL, RETRIEVER, GUARDRAIL, MCP_TOOL), LLM spans come from wrap, the Verifier should be a GUARDRAIL span.
2. `NEATLOGS.md` section 5: run labels use `tags` in init (one process per evidence run), not a different workflow name.
3. `NEATLOGS.md` section 1 step 3: the skill name is on the PyPI page. The underscore name written there was a guess. Copy the real name.
4. `ENTIRE.md` Step 0: Antigravity IS supported, through the Antigravity CLI. Use the CLI for coding sessions.
5. `ANTIGRAVITY_SETUP.md`: Entire writes hooks to `.agents/hooks.json`, which suggests the Antigravity project folder may be `.agents` and not `.agent`. VERIFY the rules and workflows folder names, and place our rule files where Antigravity actually loads them.
6. `AGENTS.md` and Entire graph: the entire graph agent setup command adds managed blocks to `AGENTS.md`. Let it, but do not let it overwrite our rules.
7. `ARCHITECTURE.md`: Python must be 3.10 to 3.13 for neatlogs. Add Go to the setup list if we use entire graph. The Researcher may call the Crustdata Web APIs, with the cache as fallback.
8. `CFO_PLAN.md`: add a step to build a shared read only Page, and add Crustdata credits per scholarship as a cost input.
9. `TASKS.md`: add a smoke test task at 8:15 AM for Entire plus Antigravity CLI capture, and a B02 check that Gemini through the OpenAI compatible client is traced with correct model and tokens.

## 8. First hour smoke tests (Saturday, before building anything)

1. [ ] Entire: install, check `entire agent list` includes antigravity, enable, make a test commit through the Antigravity CLI, confirm a checkpoint exists and status is enabled. Time box 20 minutes. If it fails, ask in Discord immediately.
2. [ ] neatlogs: init, one wrapped Gemini call, one WORKFLOW span with a nested AGENT and TOOL span, run the doctor check, see the trace in the dashboard. Time box 20 minutes.
3. [ ] neatlogs MCP: add the MCP entry to Antigravity and ask it to search traces. If it cannot connect, note it and move on.
4. [ ] cfo.ai: signup, cancel, confirm credits, ask Ari one test question about the unit economics. Time box 10 minutes.
5. [ ] Crustdata: claim credits, run one web search with the scholar source and one fetch. Time box 15 minutes.
6. [ ] All four members registered on Luma with the same team name.

## 9. Sources used

1. PyPI project page for neatlogs and the neatlogs GitHub repo.
2. neatlogs docs site: Welcome, Python SDK, Tags, Custom Attributes, Experiments, Fixes and MCP Server pages.
3. neatHack page on neatlogs.com (FAQ and requirements).
4. Entire docs: Quickstart, Antigravity agent page, agent hooks configuration, capture checkpoints, entire graph overview and CLI reference. The Entire CLI GitHub repo. A GitHub issue on Antigravity IDE support in the entireio external agents repo.
5. Crustdata docs: API introduction, Web Search, Web Fetch, Web quickstart, Person Enrich, MCP page.
6. cfo.ai website and docs home page, a launch press release and a third party product profile for pricing.
