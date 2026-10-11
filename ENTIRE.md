# ENTIRE.md

How we set up Entire with the Antigravity CLI, keep it capturing, use entire graph, and collect checkpoint evidence. Corrected from the official docs (see `TOOLS_RESEARCH.md` section 2). It replaces any earlier version.

IMPORTANT: enable Entire BEFORE the first commit. Checkpoints are created on git commit.

## 1. What Entire does

1. Hooks into git and captures AI agent sessions: prompts, transcripts, tool activity, changed files and token usage.
2. Stores sessions and checkpoints on a separate branch named `entire/checkpoints/v1`, so normal history stays clean.
3. Creates a checkpoint when you or the agent make a git commit. A git hook adds an Entire checkpoint trailer to the commit message. An attribution trailer shows the share of agent written lines.
4. Multiple sessions can share one commit and are preserved separately.
5. On entire.io you browse branches, commits and checkpoints. A checkpoint shows commit, agent, files changed, AI percentage and token usage, with a Sessions tab (prompts, transcript, tool activity) and a Changes tab (diff).

## 2. Antigravity support (confirmed, with a caveat)

1. Entire documents an Antigravity integration. It captures from the ANTIGRAVITY CLI (the `agy` command), not necessarily the IDE. An older GitHub issue reported that IDE sessions were not detected.
2. Rule for us: do all code writing through the Antigravity CLI in the main conversation. Use the IDE only for reading and previews unless a test proves it is captured.
3. Subagent sessions are not attached to the parent checkpoint. Keep important work in the main conversation.
4. There is no tracking banner inside Antigravity. Check capture with Entire status and Entire doctor.

## 3. Install and enable (do this first, 20 minute time box)

Copy exact command lines from the Entire installation page and the Entire quickstart page. They contain flags with dashes that are not reproduced here.

1. [ ] Install the Entire CLI with the official installer for stable (curl script on Mac and Linux, Scoop on Windows). Result: ______
2. [ ] Install and authenticate the Antigravity CLI. Result: ______
3. [ ] Run the Entire agent list command and confirm `antigravity` is listed. If not, update Entire. Result: ______
4. [ ] In the repo root, BEFORE the first commit, enable Entire with the agent option set to antigravity (quickstart shows the exact line). For an already enabled repo use the Entire agent add command.
5. [ ] Confirm Entire manages an `entire` entry in `.agents/hooks.json`.
6. [ ] Run Entire status and Entire doctor. Both must look healthy.
7. [ ] Commit `.entire/settings.json` (shared settings). Keep `.entire/settings.local.json` local.
8. [ ] Smoke test: make a tiny change through the Antigravity CLI, commit, and confirm a checkpoint exists on `entire/checkpoints/v1` and the commit message has the Entire trailer. Result: ______
9. [ ] Make sure the checkpoints branch is pushed to GitHub (default session pushing should do it, check the Entire settings for the push option). Confirm on GitHub that the branch is visible.
10. [ ] Repeat steps 1 to 7 on Ayo's machine so his commits are captured too.
11. [ ] If the prompt asks whether to link commits to an active session, choose always for this repo.

If the smoke test fails, ask in the neatHack Discord right away. Fallback agents Entire supports: Claude Code, Codex, Copilot CLI, Cursor, Factory, OpenCode and Pi. Never claim a checkpoint exists if it does not.

## 4. Daily routine

1. One Antigravity CLI conversation per task ID. Commit right after the task so the checkpoint matches the change.
2. Small commits with the format in `AGENTS.md` section 6, with a reasoning line in the body.
3. Never squash or rewrite published history. Never delete the checkpoints branch.
4. Push at least hourly.
5. Never paste API keys or real personal data into the agent. The session is stored on a branch that is public if the repo is public.
6. Each evening, compare checkpoint count with commit count.

## 5. entire graph (code map for the agent)

1. entire graph is a plugin for the Entire CLI. It builds a local, deterministic map of functions, types, routes and call relationships. It does not send code to any model or service.
2. It needs the Go toolchain. Install Go, then install the plugin using the lines on the Entire page "Install and Enable entire graph".
3. After our own `AGENTS.md` is committed, run the entire graph agent setup command. It writes a graph guide inside the `.entire` folder and adds managed blocks to `AGENTS.md` and `CLAUDE.md`. Review the diff and keep our rules intact.
4. Confirm language coverage with the capabilities command (JSON output) and check that Python and TypeScript appear in the semantic languages list.
5. Useful commands: index, impact (what a change could affect), neighbors, def, explain, diff (entity level changes), commit, checkpoint (analyze the commit linked to a checkpoint), stats (token saving estimate, a local heuristic and not a benchmark), doctor. The verify command runs a command you give it with your privileges, so use it carefully.
6. Use it in two ways: ask Antigravity for impact analysis before editing `llm.py`, `coordinator.py` or the API contract, and capture graph diff or impact output for the Verifier change as evidence.
7. Dynamic behavior (reflection, generated code) can be missed. Treat the graph as a guide, not a guarantee.

## 6. Evidence to collect

1. [ ] Entire status output after setup (Saturday morning).
2. [ ] Which agent option was used and the confirmation that checkpoints appear.
3. [ ] The entire.io branch view with checkpoints: Saturday evening, Sunday night, Monday morning.
4. [ ] One checkpoint opened in detail for the Verifier change: Sessions tab (prompts and reasoning) and Changes tab, plus AI percentage and token usage. Note the commit hash.
5. [ ] entire graph output (impact or diff) saved to `docs/evidence/entire_graph.txt` or as an image, plus the stats output labeled as an estimate.
6. [ ] The checkpoints branch visible on the public GitHub repo.
7. [ ] First commit timestamp showing it is after the hackathon start.
8. [ ] A note on any commits made without a checkpoint.

## 7. Demo coverage for Entire (about 20 seconds)

1. Architecture: the checkpoints branch next to main.
2. Implementation: Antigravity CLI hooks and the commit trailer.
3. Runtime: checkpoints growing over the 48 hours.
4. Reasoning: open the Verifier checkpoint and read the context.
5. Result: attribution percentage and the graph impact or diff output.

## 8. Troubleshooting

1. No checkpoints after commits: run Entire status and Entire doctor. Check `.agents/hooks.json`. Confirm you used the Antigravity CLI and not only the IDE.
2. Repair the integration by running the Entire agent add command again for antigravity, then Entire doctor.
3. GUI git clients cannot find `entire` from hooks: commit from the terminal.
4. Branch missing on GitHub: push it explicitly.
5. Token usage missing: it depends on the `agy` command being on the PATH when Entire is set up. Rerun setup after fixing the PATH.
6. Do not rewrite or delete the checkpoints branch.

## 9. Honesty note

If some commits were made by hand without the agent, they may have no useful context. Say so in `EVIDENCE.md`.
