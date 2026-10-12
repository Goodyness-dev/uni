# NEATLOGS_IMPROVEMENT_V1

User-authorized scope: launch Neatlogs factuality Evals on actual fictional traces, investigate a real failing trace and dispatch an accepted fix through a supported connected coding provider, and version/test/promote the drafting prompt with real runtime readback. No new applicant data, screens, endpoints or dependencies.

Implementation order:
1. Dashboard: span-level Evals scoped to scholarpilot + factuality_evaluation + LLM, rubric rejects unsupported causation, role inflation and accomplished aspirations; save actual judgments and linked traces.
2. app/agents/generation.py: extract drafting prompt constant and resolve production through the existing SDK; app/core/tracing.py owns async managed_drafting_prompt(fallback: str) -> tuple[str, dict], logs explicit fallback when unavailable. Keep required grounding rules locally enforced. Tests cover resolution, fallback and protected grounding.
3. scripts/neatlogs_improvement.py: seed baseline/candidate versions, compare generated factuality on fictional fixtures, promote only passing candidate, prove production readback and a subsequent actual call; record version and digest. No invented metrics.
4. Dashboard Investigate/Fixes: use an actual failed trace, review proposed change, dispatch only via an already authorized supported provider; verify resulting PR and relevant tests. If GitHub/provider setup requires new sensitive access or credentials, record exact blocker and hand off that setup.

Spans: managed_prompt_fetch TOOL, recovery_decision CHAIN, prompt_validation WORKFLOW, existing llm_tailor_v1 CHAIN and wrapped LLM. Tests offline/no real keys; root suite and backend quick check before commit. Evidence records partial failures truthfully.

## Actual results and review

Neatlogs managed drafting versions 1 (baseline) and 2 (candidate) are saved. Both produced zero unsupported segments in the small live comparison; this is not evidence of improved accuracy. Version 2 was promoted and a subsequent real model call used it (trace 49f59e1ca619637855dc76dfbd93e6f1). AWS deployment succeeded and the API container fetched production version 2 with matching digest and readiness checks. Rollback: move production to version 1 with neatlogs.update_prompt; runtime fetches production without a stale cache. Mandatory local grounding instructions and all three verification gates remain enforced.

Real Evals batch 9459a6ed-ac56-4cea-a14a-0261bc2a7c47 completed 13/13 answers: four pass, eight fail, one insufficient_evidence. A sampled failure is a false format judgment: the SDK renders schema-valid JSON as readable text. Do not report these as factuality accuracy. A second six-case batch uses exact fictional claim/source and actual provider verdict on the root trace, explicitly ignoring dashboard formatting. Saved evidence links each case to its actual trace.

Fixes MCP returned actual card 05bbb6f2-1f03-4ff4-8d20-70f25e86f135. Its suggested deterministic-only acceptance/threshold bypass is rejected. A deterministic pass is necessary but insufficient: independent judge and Challenger must also pass. The review adds stage-specific counts and four regression combinations while retaining the exact admission condition. A PR is produced by this Codex session via MCP review, not by Neatlogs automatic cloud dispatch. Native dispatch remains blocked: no coding-agent API credentials, and Investigate repeatedly reported connection lost with Fast, Pro and approved/verified Gemini BYOK. No fabricated investigation or dispatch success.

Validation: 143 offline root tests; 99 backend quick-check tests. Frontend unchanged. The newest diagnostic additions are reviewable in the PR; the managed prompt resolver is already deployed on AWS.
