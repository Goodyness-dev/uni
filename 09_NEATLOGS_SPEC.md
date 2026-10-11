# 09_NEATLOGS_SPEC.md

How neatlogs is used, exactly. Sections 1 to 5 are needed from task B02. Sections 6 to 10 are the depth work (B14, B16, B17, B22, B24).

Facts below come from the neatlogs docs (Python SDK, Span Kinds, Custom Attributes, Tags, Traces, Detections, Investigate, Fixes, MCP, Doctor). Items marked VERIFY could not be confirmed and need a quick test.

## 1. Setup facts

1. Python must be 3.10 or newer and below 3.14. Use 3.11 or 3.12.
2. `neatlogs.init(...)` is called ONCE per process. Parameters we use: `api_key`, `workflow_name`, `tags`, `capture_logs`, and `endpoint` for EU projects (`https://eu.ingest.neatlogs.com`, base URL only).
3. Calling `init` again with the same configuration is harmless. Calling it with different configuration raises a configuration error. So init lives only in `tracing.py`, and each evidence run is its own process.
4. `neatlogs.wrap(client)` wraps an LLM client so each call becomes an LLM span with prompt, response, tokens, latency and model.
5. `@neatlogs.span(kind=..., name=...)` decorates our own functions. Allowed kinds, UPPERCASE only: `WORKFLOW`, `AGENT`, `CHAIN`, `TOOL`, `RETRIEVER`, `EMBEDDING`, `GUARDRAIL`, `MCP_TOOL`. Any other value raises an error.
6. `with neatlogs.trace(name, kind=...) as span:` opens an inline span. `span.set_attribute(key, value)` sets attributes.
7. `neatlogs.log("message with {placeholders}", level=..., key=value)` writes a structured log line inside the active span (needs `capture_logs=True` in init). VERIFY the exact signature.
8. `neatlogs.flush()` and `neatlogs.shutdown()` at the end of scripts and once at server shutdown. Never per request.
9. A parentless span of kind WORKFLOW, CHAIN, AGENT, MCP_TOOL or LLM is a trace root. A standalone TOOL, GUARDRAIL or RETRIEVER gets an automatic WORKFLOW parent. We always give runs an explicit WORKFLOW root.
10. Tags set in init apply to every trace from that process. They are the run labels (`run_A`, `run_B`, `run_C`, `evidence`, `eval`).
11. Custom attributes: GUARDRAIL spans use `neatlogs.guardrail.input`, `neatlogs.guardrail.passed` (true or false, shown as Passed or Blocked) and `neatlogs.guardrail.output`. TOOL spans use `neatlogs.tool.name`, `neatlogs.tool.description`. RETRIEVER spans use `neatlogs.retriever.query`, `neatlogs.retriever.top_k` and documents. Our own attributes use plain names (`run_id`, `mode`, and so on, section 5). VERIFY that plain attribute names appear in the span detail panel and can be used in Detection conditions. If they do not, prefix them with `neatlogs.` and update `10_FAILURES_AND_RECOVERY.md` section 6.
12. Session Replay is experimental and one trace equals one session. We do not rely on multi trace sessions.

## 2. Span map (what gets which kind and name)

1. Run entry (`coordinator.execute_run`): `WORKFLOW`, name `scholarpilot_run`.
2. Agents (`intake`, `matcher`, `researcher`, `edge_finder`, `tailor`, `verifier`, `applier`, `packager`): `AGENT`, names exactly `agent_intake`, `agent_matcher`, `agent_researcher`, `agent_edge_finder`, `agent_tailor`, `agent_verifier`, `agent_applier`, `agent_packager`, with `role` and `goal` text.
3. Scout and the dossier cache read: `RETRIEVER`, names `retrieve_listings` and `retrieve_dossier_cache`.
4. Verifier rounds: `GUARDRAIL`, name `verification_round`. Challenger: `GUARDRAIL`, name `adversarial_challenge`.
5. Everything that is not an LLM call: `TOOL` with `tool_name`: `hard_rules`, `strip_sensitive`, `fetch_page`, `deterministic_claim_check`, `blocker_check`, `portal_draft`, `portal_submit`, `portal_confirm`, `send_email`, `send_telegram`, `telegram_callback`, `build_package`, `sqlite_write` (use sparingly, only for status changes).
6. LLM calls: each call goes through `call_llm`, which opens a `CHAIN` span named `llm_<prompt_id>` (for example `llm_tailor_v1`) as the parent, and the wrapped client creates the LLM child span automatically.
7. Recovery decisions: `CHAIN` span named `recovery_decision`.
8. Retries and fallbacks: each attempt is a sibling LLM span under the same `llm_<prompt_id>` parent. The fallback call is a sibling, never nested inside the failed attempt.

Target tree for one application:

```
WORKFLOW scholarpilot_run
  AGENT agent_intake
    CHAIN llm_intake_v1
      LLM (wrapped client call)
  RETRIEVER retrieve_listings
  AGENT agent_matcher
    TOOL hard_rules
    CHAIN llm_matcher_v1
  AGENT agent_researcher
    RETRIEVER retrieve_dossier_cache  (or TOOL fetch_page plus CHAIN llm_researcher_v1)
    CHAIN recovery_decision          (only when research failed)
  AGENT agent_edge_finder
    TOOL strip_sensitive
    CHAIN llm_edge_v1
  AGENT agent_tailor
    CHAIN llm_tailor_v1
  AGENT agent_verifier
    CHAIN llm_verifier_extract_v1
    TOOL deterministic_claim_check
    CHAIN llm_verifier_judge_v1
    GUARDRAIL verification_round     (one per round)
    CHAIN llm_tailor_revise_v1       (when revising)
    GUARDRAIL adversarial_challenge
  AGENT agent_packager
    TOOL build_package
  AGENT agent_applier
    TOOL portal_draft
    TOOL blocker_check
    CHAIN recovery_decision          (handoff, fallback)
    TOOL portal_submit
    TOOL portal_confirm
    TOOL send_telegram
```

## 3. tracing.py (copy this, then adapt imports)

Notes: no return annotations are shown here to keep the code simple. In the real file add type hints as the repo rules require.

```python
import functools
from contextlib import contextmanager

from app.config import settings

try:
    import neatlogs
except ImportError:
    neatlogs = None

_enabled = False


class _NoSpan:
    def set_attribute(self, key, value):
        return None


def init_tracing(tags=None):
    global _enabled
    if _enabled:
        return True
    if neatlogs is None or not settings.neatlogs_configured:
        return False
    kwargs = {
        "api_key": settings.neatlogs_api_key,
        "workflow_name": "scholarpilot",
        "tags": list(tags or []),
        "capture_logs": True,
    }
    if settings.neatlogs_endpoint:
        kwargs["endpoint"] = settings.neatlogs_endpoint
    neatlogs.init(**kwargs)
    _enabled = True
    return True


def shutdown_tracing():
    if _enabled and neatlogs is not None:
        neatlogs.flush()
        neatlogs.shutdown()


def tracing_enabled():
    return _enabled


def wrap_client(client):
    if _enabled and client is not None:
        return neatlogs.wrap(client)
    return client


def _clean(value):
    if value is None:
        return None
    if isinstance(value, bool) or isinstance(value, int) or isinstance(value, float):
        return value
    if isinstance(value, (list, tuple, set)):
        return ", ".join(str(v) for v in value)
    return str(value)


def set_attrs(span, **kwargs):
    for key, value in kwargs.items():
        cleaned = _clean(value)
        if cleaned is not None:
            span.set_attribute(key, cleaned)


def _lazy_span(kind, name, **extra):
    def decorator(fn):
        holder = {}

        @functools.wraps(fn)
        def inner(*args, **kw):
            if not _enabled:
                return fn(*args, **kw)
            if "wrapped" not in holder:
                holder["wrapped"] = neatlogs.span(kind=kind, name=name, **extra)(fn)
            return holder["wrapped"](*args, **kw)

        return inner

    return decorator


def workflow_span(name):
    return _lazy_span("WORKFLOW", name)


def agent_span(name, role=None, goal=None):
    extra = {}
    if role:
        extra["role"] = role
    if goal:
        extra["goal"] = goal
    return _lazy_span("AGENT", "agent_" + name, **extra)


def tool_span(tool_name, description=None):
    extra = {"tool_name": tool_name}
    if description:
        extra["description"] = description
    return _lazy_span("TOOL", tool_name, **extra)


def retriever_span(name):
    return _lazy_span("RETRIEVER", "retrieve_" + name)


@contextmanager
def trace_block(name, kind, **attrs):
    if not _enabled:
        yield _NoSpan()
        return
    with neatlogs.trace(name, kind=kind) as span:
        set_attrs(span, **attrs)
        yield span


class _Guardrail:
    def __init__(self, span):
        self.span = span

    def set_result(self, passed, input_text, reason):
        self.span.set_attribute("neatlogs.guardrail.passed", bool(passed))
        self.span.set_attribute("neatlogs.guardrail.input", str(input_text)[:2000])
        self.span.set_attribute("neatlogs.guardrail.output", str(reason)[:1000])

    def attrs(self, **kwargs):
        set_attrs(self.span, **kwargs)


@contextmanager
def guardrail(name):
    with trace_block(name, "GUARDRAIL") as span:
        yield _Guardrail(span)


@contextmanager
def llm_call_span(prompt_name, system, user, ctx):
    with trace_block(
        "llm_" + prompt_name,
        "CHAIN",
        run_id=getattr(ctx, "run_id", None),
        application_id=getattr(ctx, "app_id", None),
        mode=getattr(ctx, "mode", None),
        listing_id=getattr(ctx, "listing_id", None),
        prompt_version=prompt_name,
    ) as span:
        yield span


class _Recovery:
    def __init__(self, span):
        self.span = span

    def decide(self, chosen, reason):
        set_attrs(self.span, **{"recovery.chosen": chosen, "recovery.reason": reason})
        log_event("Recovery chosen: {chosen} because {reason}", chosen=chosen, reason=reason)

    def finish(self, outcome):
        set_attrs(self.span, **{"recovery.outcome": outcome})


@contextmanager
def recovery_decision(trigger, options):
    with trace_block("recovery_decision", "CHAIN") as span:
        set_attrs(span, **{"recovery.trigger": trigger, "recovery.options": options})
        yield _Recovery(span)


def log_event(message, **kwargs):
    if not _enabled:
        return
    try:
        neatlogs.log(message, **kwargs)
    except Exception:
        return None
```

Behavior requirements:
1. Everything is a safe no op when neatlogs is missing or no key is configured (tests rely on this).
2. The span decorators decide at CALL time whether tracing is enabled (the `_lazy_span` pattern), because decorators run at import time before `init_tracing`.
3. `wrap_client` is used by `llm.py` when creating clients (after `init_tracing`).
4. If a neatlogs call raises an unexpected error, tracing must never crash the app. Wrap risky calls in `try` and `except Exception` and continue.
5. The `recovery_decision` helper is used together with `db.add_event` (see `04_ARCHITECTURE.md` section 8). Create one function `coordinator.record_recovery(ctx, trigger, options, chosen, reason, outcome)` that does the span, the event and the log line together so every recovery is recorded the same way.

## 4. Where each helper is applied

1. `coordinator.execute_run`: `@workflow_span("scholarpilot_run")`.
2. Each agent module entry function: `@agent_span("<name>", role="...", goal="...")`.
3. `scout.load_listings`: `@retriever_span("listings")`. Dossier cache read: a `retrieve_dossier_cache` retriever span.
4. `matcher.hard_rules`, `sensitive.strip_sensitive` call sites, `researcher.fetch_page_text`, `verifier.deterministic_check`, `applier.check_blockers`, `notify.send_telegram`, `notify.send_email`, portal HTTP calls in the Applier: `@tool_span("<tool_name>")`.
5. Verifier rounds: `with guardrail("verification_round") as g:` then `g.set_result(...)` and `g.attrs(round=..., claims_checked=..., claims_unsupported=...)`. Challenger: `guardrail("adversarial_challenge")` with `claims_overturned`.
6. Every LLM call: inside `llm.call_llm` via `llm_call_span`.

## 5. Attributes (names and where)

On every span created through our helpers inside a run (set via `trace_block` attrs or `set_attrs`): `run_id`, `application_id`, `mode`, `listing_id`.

LLM chain spans: `prompt_version`, `model`, `attempt`, `fallback_used`, `json_repaired`, `tokens_in`, `tokens_out`, `cost_usd`.
Matcher: `fit_score`. Edge Finder: `edges_selected`, `edges_dropped`. Researcher: `source` (cache or live), `snippets_dropped`, `injection_dropped`, `credits_used`. Tailor: `segments`, `essay_words`.
Verifier guardrails: `round`, `claims_checked`, `claims_unsupported`, `claims_removed`, `claims_overturned`.
Applier: `channel`, `blocker` (none, captcha, login, portal_500), `confirmed`.
Failure injection: `failure_injected` set to the flag name on the span where it happened.
Recovery decisions: `recovery.trigger`, `recovery.options`, `recovery.chosen`, `recovery.reason`, `recovery.outcome`.

Privacy: for the synthetic persona full inputs and outputs are captured (good for the demo). For real users use `capture_input=False` or `mask` options on spans that handle personal text, and never log full CV text in attributes.

## 6. Recovery decisions, logs and the product link

1. Every recovery follows `04_ARCHITECTURE.md` section 8 and uses `coordinator.record_recovery`. The `reason` is one honest sentence that names the evidence (for example: rate limited twice in a row, so switching to the backup model).
2. Structured logs (`log_event`) at: edge selected (fact id and reason), claim removed (reason), claim overturned, channel chosen, blocker found, handoff sent, confirmation seen, recovery chosen.
3. `trace_url`: set `settings.neatlogs_dashboard_url` (default `https://app.neatlogs.com`, EU `https://eu.app.neatlogs.com`). If the SDK exposes the current trace id VERIFY (look for a get trace id style call in the Python SDK page), build a link to that trace. If not, store the dashboard URL and the tag filter text in the `trace_url` field and let the UI label the button Open neatlogs. Say which one you used in `17_EVIDENCE_CHECKLIST.md`.
4. Prompt templates: attaching `SystemPromptTemplate` and `UserPromptTemplate` to LLM spans is a stretch (VERIFY the parameter names for the trace call). If it works, attach them in `llm_call_span`. If not, the prompt id in the span name and `prompt_version` attribute is enough.

## 7. The improvement loop (the neatlogs plus Entire story)

Loop 1 (B14 to B17):
1. Run A (mode A, tags `run_A,evidence`), captured BEFORE the enforcement code exists.
2. In the Antigravity CLI use `/read_trace` (neatlogs MCP): find the latest `run_A` trace, list GUARDRAIL spans that did not pass, the claim text and the source ids.
3. The fix is the enforcement loop (B15). Commit with the reasoning in the body (Entire checkpoint).
4. Run B (mode B, tags `run_B,evidence`). Compare.

Loop 2 (B24):
1. After the failure injections, read the slowest or most expensive application trace and the recovery traces.
2. Choose ONE real improvement the trace shows (examples: fewer tokens in the judge prompt, batching claims, skipping a retry that never helps).
3. Implement, run with tags `run_C,evidence`, compare cost and latency with run B.

The log file `docs/evidence/improvement_log.md` has one entry per loop with: date and time, trace link, the finding (copy the evidence), the change, the commit hash, the Entire checkpoint id, before numbers, after numbers.

MCP setup (from `03_TOOLS_SETUP.md` section 3): streamable HTTP, the neatlogs ingest host plus the MCP path, project key as bearer token. Tools available: search traces, get full trace context, list detections and trends, list and read fix suggestions, accept or dismiss, push a trace. If MCP does not connect to Antigravity, use the dashboard and the neatlogs CLI (traces list, traces get, spans list) and say so. Fix dispatch to a cloud coding agent is not available for Antigravity, so we do not use it.

## 8. Run labeling and the evidence runs

1. One process per evidence run through `scripts/run_pipeline.py <mode> <top_n> <tags>`. The script calls `init_tracing(tags)` first.
2. Tag conventions: `run_A`, `run_B`, `run_C`, plus `evidence`. Evaluation runs: `eval`, `eval_v1`, `eval_v2`. Failure injection runs: `recovery` plus the flag name.
3. Run each mode at least twice. Report both runs or medians. Never cherry pick.
4. Compare in the dashboard by filtering by tag. VERIFY whether Analytics can compare two tags side by side. If not, screenshot each filtered view and put the numbers in a table.
5. Metrics come from our own `RunMetrics` and from neatlogs Analytics. If neatlogs does not price the fallback provider, our computed cost is the source and we say so.

## 9. Troubleshooting

1. No traces at all: run the doctor local check, then the probe check (docs page SDK Doctor), check the key and the region endpoint, check `init_tracing` runs before the first span.
2. Each call is its own trace: the entry point lacks the WORKFLOW decorator, or the decorator ran before init (use the lazy pattern above).
3. Spans missing in the background thread: create the WORKFLOW span INSIDE the thread function (`execute_run` is the thread target, so decorate `execute_run`, not the function that starts the thread). VERIFY in the first trace.
4. Short scripts lose spans: call `shutdown_tracing()` at the end.
5. Gemini call shows the wrong model, zero tokens or no cost: switch the primary client to the Google GenAI SDK (create it after init, wrap it with `neatlogs.wrap`) and keep `call_llm` unchanged. If cost is still missing, rely on our computed `cost_usd` attribute.
6. Plain attribute names not visible or not usable in Detections: prefix with `neatlogs.`.
7. Conflicting init error: init was called with different tags in the same process. Use a new process.
8. Double counted LLM spans: the client is wrapped twice. Wrap once in `llm.py` only.

## 10. Depth features to use (B22 and B24)

1. **Detections:** create the 15 rules from `10_FAILURES_AND_RECOVERY.md` section 6. Screenshot the traces list with badges.
2. **Investigate:** use the prompts in `10_FAILURES_AND_RECOVERY.md` section 7 (Fast mode for simple, Pro mode for broad). Save one thread with its linked evidence. Connect GitHub under Settings then Tools and MCPs so Neat Agent can read repo files.
3. **Analytics:** screenshots of cost by agent and tool, latency, errors, detection trend. These feed `16_CFO_AND_CRUSTDATA.md`.
4. **Voting:** thumbs up or down on Tailor outputs and removed claims in a few traces, then screenshot the filtered view.
5. **Comments:** Memeshi and Ayo comment on the important spans (the run A finding, a recovery decision, the handoff pause). Screenshot one thread.
6. **Evals:** try sending a few Tailor traces to an AI evaluator for essay quality if available on our plan. If not, skip.
7. **Session Replay:** replay the CAPTCHA handoff run once for the demo. Experimental, so keep it optional.
8. **Evaluation script:** `scripts/eval_runs.py` (see `07_AGENTS_SPEC.md` section 12.5) with tags `eval,eval_v1`, then again after loop 2 with `eval_v2`.
9. **Comments and votes are evidence of team use,** so do them while debugging, not as a last minute chore.

## 11. How neatlogs is made obvious to the judges

1. Show a neatlogs trace in the first 20 seconds of the video, with a caption.
2. Make the improvement loop the centerpiece of the neatlogs segment (trace, Antigravity reads it, fix, Entire checkpoint, new trace).
3. The product shows a View trace (or Open neatlogs) button, the run metrics strip, and recovery decisions with reasons in the timeline.
4. The README has a neatlogs section with screenshots (span tree, guardrail passed and blocked, detections, A versus B, improvement log).
5. Every public post carries a neatlogs screenshot with a new finding.
6. Ask in the Discord how judges will view traces. If project sharing is not possible, the screenshots and `improvement_log.md` in the repo are the proof.
