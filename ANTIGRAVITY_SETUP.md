# ANTIGRAVITY_SETUP.md

How to run Google Antigravity as our coding agent for 48 hours without it wrecking the repo, wasting time, or breaking the hackathon rules.

NOTE: Antigravity is new and its features change. Items marked VERIFY must be checked in the Antigravity docs or settings before relying on them.

IMPORTANT UPDATES FROM RESEARCH (see `TOOLS_RESEARCH.md`):
1. Entire captures sessions from the Antigravity CLI (the `agy` command). Do all code writing through the CLI so checkpoints exist. Use the IDE only for reading, previews or work you do not need as evidence, unless a test commit proves the IDE is captured.
2. Entire writes its hooks to `.agents/hooks.json`, so Antigravity's project folder may be `.agents` and not `.agent`. Check which folder your version loads for rules, workflows and skills, and place the files from sections 4 and 5 there. Confirmed folder: ______
3. Add the neatlogs MCP server to Antigravity's MCP settings so the agent can read traces (details in `NEATLOGS.md` section 6).
4. The entire graph setup command adds managed blocks to `AGENTS.md`. Let it, but keep our rules intact.

## 1. How Antigravity reads instructions

1. **Rules** are always on instructions for the workspace. Workspace rules live in `.agent/rules/` as markdown files (VERIFY the folder name in your version). Global rules live in the user's Gemini config folder and apply to every project. We use workspace rules only.
2. **Workflows** are saved prompts you trigger by typing a slash command in the agent panel. They live in `.agent/workflows/` (VERIFY). We use them for repeated jobs such as committing a task and running the A and B comparison.
3. **Skills** are folders with a `SKILL.md` that the agent loads when relevant. The neatlogs skill is installed this way (see `NEATLOGS.md`).
4. **Root AGENTS.md**: newer versions read an `AGENTS.md` at the repo root (VERIFY). To be safe, we keep `AGENTS.md` at the root AND a short rule file in `.agent/rules/` that tells the agent to read it first.

## 2. Recommended settings

1. **Planning mode for anything touching more than one file.** The agent produces an implementation plan artifact and a task list artifact. Read the plan before approving. Reject plans that add features not in `TASKS.md`.
2. **Fast mode only for tiny edits** (rename, copy fix, styling tweak).
3. **Review policy**: set artifact review to "request review" for plans, so the agent never starts a big change without you reading the plan.
4. **Terminal policy**: set to require approval for commands (not auto run everything). Specifically block or manually approve: `rm`, `git push`, `git reset`, `git checkout` of files, `pip install` of anything not listed in `ARCHITECTURE.md`, and any command that reads `.env`.
5. **Secrets**: add `.env` and `backend/data/vault/` to the ignore settings if Antigravity has a file access deny list (VERIFY). Never paste API keys into chat.
6. **Browser agent**: allowed for UI smoke tests of `localhost:3000` only. It must not browse real scholarship portals or submit anything on the open web.
7. **Model choice**: use the strongest available model for planning and for the Verifier and Tailor code. A faster model is fine for UI polish. Note the model used in the commit body when it matters for the Entire evidence.

## 3. Working agreement for two people on one repo

1. **Ownership**: Memeshi owns `backend/` and `data/`. Ayo owns `frontend/` and the demo portal templates in `backend/portal/`. Nobody edits the other's folder without telling them in chat.
2. **Contract first**: both build against `ARCHITECTURE.md` section 9 (API contract). If either side needs a contract change, edit `ARCHITECTURE.md` in its own small commit with the message prefix `contract:` and tell the other person immediately.
3. **Branching**: work on `main` with small commits, and always run `git pull` with rebase before pushing. We have two people and 48 hours, so no long lived branches.
4. **One Antigravity conversation per task ID** from `TASKS.md`. Name the conversation with the task ID, for example "B07 Matcher". Do not reuse a long conversation for unrelated work, because context drift causes invented code.
5. **Commit after every task**, using the `/commit_task` workflow. Entire creates a checkpoint on each commit, so small commits give us good evidence.
6. **Mocks for the frontend**: until the backend is ready, Ayo runs against `frontend/mocks/` JSON that matches the contract exactly (`USE_MOCKS=true`).

## 4. Rule files to create in `.agent/rules/`

Create each file below with the exact content shown.

### 4.1 `.agent/rules/00_read_first.md`

```
Before doing any work in this repository, read these files in order:
1. AGENTS.md (the rules you must follow)
2. PROJECT.md (what we are building and what we are not)
3. ARCHITECTURE.md (structure and API contract)
4. TASKS.md (find the task ID you were given and only do that task)
Never start work without a task ID. If the request has no task ID, ask which task it belongs to.
Never add features that are not in TASKS.md. Put ideas in a Stretch note instead.
```

### 4.2 `.agent/rules/01_grounding_and_safety.md`

```
This product writes scholarship applications. The most important rule in the project:
NEVER invent experience, credentials, grades, awards, hours, names, dates or numbers about the applicant.
Every sentence in generated CV or essay text must be traceable to one of three sources:
the CV facts, the Profile Vault facts, or the research dossier.
Never write code that fabricates a fact to make a demo look better.
Never bypass or solve a CAPTCHA. Detect it, stop, and hand off to the user.
Never submit to a real scholarship portal. Only the demo portal and our own email inbox can receive submissions.
Never use sensitive facts (religion, disability, health, family income) unless the listing requires them and the profile consent flag is true. This is enforced in code in the sensitive filter, not only in prompts.
```

### 4.3 `.agent/rules/02_tracing.md`

```
Every agent function and every LLM call and every tool call must be wrapped in a neatlogs span, using the helpers in backend/app/tracing.py.
Do not call the LLM SDK directly. Always call backend/app/llm.py, which handles tracing, retries, JSON repair and fallback.
Every span must record the application id, the run id, and the run mode (A or B) as metadata.
Read NEATLOGS.md before touching any instrumentation code.
```

### 4.4 `.agent/rules/03_git_and_commits.md`

```
Make small commits, one per finished task or sub task. Entire creates one checkpoint per commit, so commits are our evidence.
Commit message format: "<type>(<area>): <what> [<task id>]" where type is feat, fix, test, docs, chore or contract.
Example: "feat(verifier): claim extraction with CV citations [B12]".
Never use git push force. Never rewrite history. Never commit .env, data/vault, or any file with a token.
Never commit code in a state that does not start. Run the quick check command from AGENTS.md before committing.
```

### 4.5 `.agent/rules/04_scope.md`

```
We are two people with about 5 hours each per day. Scope is ruthlessly small.
Do not add authentication, accounts, deployment, Docker, web scraping of live scholarship sites, or extra screens.
Prefer plain Python and the standard library. Add a dependency only if ARCHITECTURE.md lists it.
If a task is taking more than its time box in TASKS.md, stop and report instead of expanding the design.
```

## 5. Workflow files to create in `.agent/workflows/`

### 5.1 `.agent/workflows/commit_task.md`

```
Steps to run when the user types /commit_task with a task ID:
1. Run the quick check command from AGENTS.md section 8 and confirm it passes. If it fails, fix it first.
2. Run git status and list changed files. Confirm no .env, no vault data, no tokens, no large files.
3. Stage only files related to the task.
4. Commit using the format in .agent/rules/03_git_and_commits.md, including the task ID.
5. Tick the task checkbox in TASKS.md in the same commit.
6. Report the commit hash, then stop. Do not push unless asked.
```

### 5.2 `.agent/workflows/run_ab.md`

```
Steps to run when the user types /run_ab:
1. Confirm the backend starts and the synthetic persona is loaded.
2. Run the pipeline in mode A (verifier enforcement off, audit on) for the top 2 listings using the CLI script backend/scripts/run_pipeline.py.
3. Save the neatlogs run link and the metrics JSON printed by the script into docs/evidence/run_A.json.
4. Run the pipeline in mode B (verifier enforcement on) the same way and save docs/evidence/run_B.json.
5. Print a comparison of unsupported claims, tokens, cost and latency for A versus B.
6. Do not change any code during this workflow. It only runs and records.
```

### 5.3 `.agent/workflows/verify_contract.md`

```
Steps to run when the user types /verify_contract:
1. Read section 9 of ARCHITECTURE.md (API contract).
2. For each endpoint, call the running backend and compare the real JSON shape with the documented shape.
3. Compare frontend/lib/types.ts with the documented shapes.
4. List every mismatch. Do not fix anything automatically. Ask which side should change.
```

### 5.4 `.agent/workflows/inject_failure.md`

```
Steps to run when the user types /inject_failure with a failure name (llm_429, bad_json, portal_500, captcha_wall):
1. Set the failure flag through POST /api/failure_flags (see DATA_SPEC.md).
2. Run the pipeline for one scholarship.
3. Show the event timeline for that application, including what failed and what the agent did next.
4. Clear the flag. Print the neatlogs run link so it can be saved as recovery evidence.
```

## 6. Prompt template for starting a task

Paste this into a new Antigravity conversation, replacing the task ID:

```
Task ID: B07
Read AGENTS.md, PROJECT.md, ARCHITECTURE.md, DATA_SPEC.md and AGENT_PROMPTS.md.
Do only task B07 from TASKS.md. Start in planning mode.
First give me the implementation plan as an artifact. List the files you will create or change, the functions with signatures, and how you will test it.
Wait for my approval before writing code.
After approval: implement, add or update tests, run the quick check, and show me the result.
Do not touch folders owned by the other developer.
```

## 7. How to review the agent's work (2 minute routine)

1. Read the plan artifact. Reject it if it adds scope.
2. Check that every LLM call goes through `llm.py` and every function has a span.
3. Search the diff for hard coded applicant facts. There must be none outside `data/synthetic/`.
4. Run the quick check, then `/commit_task`.

## 8. Troubleshooting

1. **Agent invents files or endpoints**: tell it to re read `ARCHITECTURE.md` section 9 and run `/verify_contract`.
2. **Agent loops on a failing test**: stop it after 2 attempts, read the error yourself, then give it the exact cause.
3. **Two agents editing the same file**: finish one conversation before starting another that touches the same folder.
4. **Rate limits on the coding model**: switch model for UI work, keep the strongest model for backend logic.
5. **Entire not capturing**: see `ENTIRE.md` troubleshooting before making more commits.
