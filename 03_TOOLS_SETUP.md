# 03_TOOLS_SETUP.md

Step by step setup for every tool, with a smoke test for each. Do this on Saturday 8:00 to 9:15 AM. Do not start building until sections 1 to 4 pass.

Exact command lines that contain flags with dashes are not copied here. Copy them from the named doc page so nothing is mistyped.

## 1. Accounts and keys checklist

1. [ ] Luma: all 4 teammates registered with the SAME team name. Web check in done. Discord joined.
2. [ ] GitHub: public repo created after 8:00 AM Saturday.
3. [ ] Gemini API key from Google AI Studio. Fallback provider key (any one of OpenAI, Anthropic or another with an OpenAI compatible endpoint).
4. [ ] neatlogs account and project API key (app.neatlogs.com, Settings then Project then API keys).
5. [ ] Telegram bot token from BotFather and your chat id.
6. [ ] Gmail app password (needs 2 step verification on) and a demo inbox address.
7. [ ] cfo.ai signup via the neatHack link, subscription cancelled immediately, credits confirmed in Discord.
8. [ ] Crustdata credits claimed (optional tool).
9. [ ] Put everything in a local `.env` that is gitignored. NEVER paste keys into Antigravity prompts.

## 2. Entire plus the Antigravity CLI (the highest risk, do it first)

Facts (from the Entire docs): Entire captures sessions from the Antigravity CLI (the `agy` command). It may not capture Antigravity IDE sessions. So all code writing goes through the CLI.

1. [ ] Install the Antigravity CLI and sign in. Result: ______
2. [ ] Install Entire with the official installer from entire.io (stable channel). Copy the exact line from the Entire installation page. Result: ______
3. [ ] Run the Entire agent list command. Confirm `antigravity` is listed. If not, update Entire. Result: ______
4. [ ] In the repo root, BEFORE the first commit, enable Entire with the agent option set to antigravity (exact line on the Entire quickstart page). Result: ______
5. [ ] Confirm hooks exist in `.agents/hooks.json` (Entire writes an `entire` entry). Note the folder name `.agents`.
6. [ ] Run Entire status and Entire doctor. Both healthy.
7. [ ] Smoke test: through the Antigravity CLI ask for a tiny harmless change (add a line to a README), commit it, then confirm: the commit message has an Entire trailer, and the branch `entire/checkpoints/v1` exists locally and on GitHub. Result: ______
8. [ ] Commit the shared Entire settings file. Keep the local settings file out of git.
9. [ ] If asked whether to link commits to an active session, choose always.
10. [ ] Repeat steps 1 to 9 on Ayo's machine.

If step 7 fails, ask in the neatHack Discord immediately. Fallback agents Entire supports: Claude Code, Codex, Copilot CLI, Cursor, Factory, OpenCode and Pi. Never claim a checkpoint exists if it does not.

Daily rules: one Antigravity CLI conversation per task id, commit right after the task, push at least hourly, never squash or rewrite history, never paste keys or real personal data into the agent (stored sessions can be public).

## 3. neatlogs

1. [ ] Python 3.11 or 3.12 virtual environment (neatlogs needs 3.10 or newer and below 3.14).
2. [ ] Install the packages listed in `04_ARCHITECTURE.md` section 3 (includes `neatlogs` and `openai`).
3. [ ] Put `NEATLOGS_API_KEY` in `.env`. EU project: also set the EU ingest endpoint in init (`https://eu.ingest.neatlogs.com`).
4. [ ] Run the neatlogs doctor local check, then the probe check. Exact lines are on the docs page SDK Doctor and the wizard page. Result: ______
5. [ ] Task B02 creates a hello trace script. Confirm in the dashboard: nested WORKFLOW, AGENT and TOOL spans, plus one real Gemini call with the real model name, tokens and latency. Result: ______
6. [ ] Install the neatlogs coding agent skill. The exact line, skill name and agent option are on the neatlogs PyPI page. If Antigravity is not an accepted agent value, install for any supported agent and copy the skill folder where Antigravity loads skills. Result: ______
7. [ ] Connect the neatlogs MCP server in Antigravity (docs page MCP Server). Streamable HTTP, the neatlogs ingest host plus the MCP path, your project key as a bearer token. Test by asking Antigravity to search your latest traces. If it fails, use the neatlogs CLI or the dashboard by hand and say so. Result: ______
8. [ ] In Settings then Tools and MCPs, connect GitHub for the repo so Neat Agent can read source files during investigations.
9. [ ] Create the 15 detections from `10_FAILURES_AND_RECOVERY.md` section 6 after the first real trace exists.

## 4. Gemini and the fallback model (a known trap)

Google is refusing Gemini 2.5 Flash for newly created keys ("no longer available to new users", official shutdown October 16, 2026). Do not trust any model id in an example.

1. [ ] Call the list models endpoint with your key and choose a current Flash or Flash Lite model it can use. Write it down: ______
2. [ ] Set `LLM_PRIMARY_MODEL` to it. Set `LLM_PRIMARY_BASE_URL` to Gemini's OpenAI compatible endpoint (copy from the Gemini API docs, VERIFY). Result: ______
3. [ ] Make one chat call with the OpenAI SDK against that base URL. If it fails with an authentication error on a new style key, switch the primary client to the Google GenAI SDK (still wrapped with neatlogs, client created AFTER neatlogs init). Result: ______
4. [ ] Repeat for the fallback provider: `LLM_FALLBACK_BASE_URL`, `LLM_FALLBACK_API_KEY`, `LLM_FALLBACK_MODEL`.
5. [ ] Check the free tier request limits for the chosen model and write them here: ______ (they decide how many test runs you can afford).

## 5. Telegram and email

1. [ ] Create the bot with BotFather, copy the token. Send any message to the bot, then call the Bot API getUpdates once to read your chat id. Result: ______
2. [ ] Test a message with the Bot API sendMessage using httpx or curl. Result: ______
3. [ ] Gmail: create an app password. Test with a 10 line smtplib script that sends to `DEMO_INBOX_EMAIL`. Result: ______

## 6. cfo.ai

1. [ ] Sign up through the link given by the hackathon (cfo.ai/neathacks). A card is required.
2. [ ] Immediately cancel the subscription in Settings then Billing. Screenshot the cancelled state.
3. [ ] Confirm in Discord that credits arrived.
4. [ ] Ask Ari one test question about unit economics to confirm it works.
5. [ ] Keep the login private, not in the repo.

## 7. Crustdata (optional)

1. [ ] Claim the hackathon credits (ask in Discord how, credits arrive after the start).
2. [ ] Test one Web Search call with the scholar source and one Web Fetch call using the Crustdata docs. Result: ______
3. [ ] Never use the human mode option (it tries to get past bot protection, which breaks our rules).
4. [ ] Put `CRUSTDATA_API_KEY` in `.env`. Time box: 45 minutes. If it is not working, use cached dossiers only.

## 8. Entire graph (optional but worth it)

1. [ ] Install Go, then install the entire graph plugin using the Entire page Install and Enable entire graph.
2. [ ] AFTER our `AGENTS.md` is committed, run the entire graph agent setup command. It adds managed blocks to `AGENTS.md` and `CLAUDE.md`. Review the diff and keep our rules intact.
3. [ ] Run the capabilities command with JSON output and confirm Python and TypeScript appear in the semantic languages.
4. [ ] Save one impact or diff output to `docs/evidence/` later (see `17_EVIDENCE_CHECKLIST.md`).

## 9. Smoke test summary (all must be green before B01)

1. [ ] Entire checkpoint exists for a test commit.
2. [ ] neatlogs doctor passes.
3. [ ] Gemini call works with the chosen model id.
4. [ ] Telegram message arrives.
5. [ ] cfo.ai signup cancelled with credits confirmed.
