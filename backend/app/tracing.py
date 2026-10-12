import functools
from collections.abc import Callable, Generator
from contextlib import contextmanager
from typing import Any

try:
    from app.config import settings
except ModuleNotFoundError:
    from app.core.config import settings

try:
    import neatlogs
except ImportError:
    neatlogs = None

_enabled: bool = False


class _NoSpan:
    """Fallback dummy span used when tracing is disabled."""

    def set_attribute(self, key: str, value: Any) -> None:
        return None


def metadata_mask(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Keep measured model metadata while excluding applicant content at export."""
    attributes = snapshot.get("attributes", {})
    safe = {"neatlogs.span.kind", "openinference.span.kind", "llm.model_name", "gen_ai.request.model",
        "gen_ai.response.model", "gen_ai.system", "application_id", "listing_id", "mode", "iteration",
        "neatlogs.tool.name", "guardrails_passed", "neatlogs.guardrail.passed", "prompt_version"}
    attributes = {key: value for key, value in attributes.items() if key in safe or key.startswith((
        "llm.token_count.", "gen_ai.usage.", "neatlogs.usage.", "code.", "neatlogs.llm.cost"))}
    return {**snapshot, "attributes": attributes, "events": []}


def init_tracing(tags: list[str] | None = None) -> bool:
    """Initialize neatlogs tracing once per process."""
    global _enabled
    if _enabled:
        return True
    api_key = getattr(settings, "neatlogs_api_key", getattr(settings, "NEATLOGS_API_KEY", None))
    endpoint = getattr(settings, "neatlogs_endpoint", getattr(settings, "NEATLOGS_ENDPOINT", None))
    if neatlogs is None or not api_key:
        return False
    kwargs: dict[str, Any] = {
        "api_key": api_key,
        "workflow_name": "scholarpilot",
        "tags": list(tags or []),
        "capture_logs": bool(getattr(settings, "NEATLOGS_CAPTURE_CONTENT", False)),
        "mask": None if bool(getattr(settings, "NEATLOGS_CAPTURE_CONTENT", False)) else metadata_mask,
    }
    if endpoint:
        kwargs["endpoint"] = endpoint
    try:
        neatlogs.init(**kwargs)
        _enabled = True
        return True
    except Exception:
        return False


def shutdown_tracing() -> None:
    """Flush and shut down neatlogs tracing at server or script exit."""
    global _enabled
    if _enabled and neatlogs is not None:
        try:
            neatlogs.flush()
            neatlogs.shutdown()
        except Exception:
            pass
        _enabled = False


def tracing_enabled() -> bool:
    """Returns True if neatlogs tracing is currently active."""
    return _enabled


def wrap_client(client: Any) -> Any:
    """Wraps an LLM client with neatlogs.wrap if tracing is enabled."""
    if _enabled and neatlogs is not None and client is not None:
        try:
            return neatlogs.wrap(client)
        except Exception:
            return client
    return client


def _clean(value: Any) -> Any:
    """Cleans an attribute value for storage in span metadata."""
    if value is None:
        return None
    if isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, (list, tuple, set)):
        return ", ".join(str(v) for v in value)
    return str(value)


def set_attrs(span: Any, **kwargs: Any) -> None:
    """Sets cleaned attributes on a span."""
    if span is None:
        return
    for key, value in kwargs.items():
        cleaned = _clean(value)
        if cleaned is not None:
            try:
                span.set_attribute(key, cleaned)
            except Exception:
                pass


def _lazy_span(kind: str, name: str, **extra: Any) -> Callable:
    """Lazy decorator that evaluates whether tracing is enabled at call time."""
    def decorator(fn: Callable) -> Callable:
        holder: dict[str, Any] = {}

        @functools.wraps(fn)
        def inner(*args: Any, **kw: Any) -> Any:
            if not _enabled or neatlogs is None:
                return fn(*args, **kw)
            if "wrapped" not in holder:
                holder["wrapped"] = neatlogs.span(kind=kind, name=name, **extra)(fn)
            return holder["wrapped"](*args, **kw)

        return inner

    return decorator


def workflow_span(name: str) -> Callable:
    """Decorates a workflow entry point with kind WORKFLOW."""
    return _lazy_span("WORKFLOW", name)


def agent_span(name: str, role: str | None = None, goal: str | None = None) -> Callable:
    """Decorates an agent module function with kind AGENT."""
    extra: dict[str, Any] = {}
    if role:
        extra["role"] = role
    if goal:
        extra["goal"] = goal
    return _lazy_span("AGENT", "agent_" + name, **extra)


def tool_span(tool_name: str, description: str | None = None) -> Callable:
    """Decorates a tool invocation with kind TOOL."""
    extra: dict[str, Any] = {"tool_name": tool_name}
    if description:
        extra["description"] = description
    return _lazy_span("TOOL", tool_name, **extra)


def retriever_span(name: str) -> Callable:
    """Decorates a document or cache retrieval with kind RETRIEVER."""
    return _lazy_span("RETRIEVER", "retrieve_" + name)


@contextmanager
def trace_block(name: str, kind: str, **attrs: Any) -> Generator[Any, None, None]:
    """Context manager opening an inline trace span with kind and attributes."""
    if not _enabled or neatlogs is None:
        yield _NoSpan()
        return
    try:
        with neatlogs.trace(name, kind=kind) as span:
            set_attrs(span, **attrs)
            yield span
    except Exception:
        raise



class _Guardrail:
    """Helper wrapper for GUARDRAIL spans."""
    def __init__(self, span: Any) -> None:
        self.span = span

    def set_result(self, passed: bool, input_text: Any, reason: Any) -> None:
        try:
            self.span.set_attribute("neatlogs.guardrail.passed", bool(passed))
            self.span.set_attribute("neatlogs.guardrail.input", str(input_text)[:2000])
            self.span.set_attribute("neatlogs.guardrail.output", str(reason)[:1000])
        except Exception:
            pass

    def attrs(self, **kwargs: Any) -> None:
        set_attrs(self.span, **kwargs)


@contextmanager
def guardrail(name: str) -> Generator[_Guardrail, None, None]:
    """Context manager opening a GUARDRAIL span."""
    with trace_block(name, "GUARDRAIL") as span:
        yield _Guardrail(span)


@contextmanager
def llm_call_span(prompt_name: str, system: str, user: str, ctx: Any) -> Generator[Any, None, None]:
    """Context manager opening a CHAIN span wrapping an LLM prompt call."""
    with trace_block(
        "llm_" + prompt_name,
        "CHAIN",
        run_id=getattr(ctx, "run_id", None),
        application_id=getattr(ctx, "application_id", None) or getattr(ctx, "app_id", None),
        mode=getattr(ctx, "mode", None),
        listing_id=getattr(ctx, "listing_id", None),
        prompt_version=prompt_name,
    ) as span:
        yield span


class _Recovery:
    """Helper wrapper for recovery_decision spans."""
    def __init__(self, span: Any) -> None:
        self.span = span

    def decide(self, chosen: str, reason: str) -> None:
        set_attrs(self.span, **{"recovery.chosen": chosen, "recovery.reason": reason})
        log_event(f"Recovery chosen: {chosen} because {reason}", chosen=chosen, reason=reason)

    def finish(self, outcome: str) -> None:
        set_attrs(self.span, **{"recovery.outcome": outcome})


@contextmanager
def recovery_decision(trigger: str, options: list[str]) -> Generator[_Recovery, None, None]:
    """Context manager opening a recovery_decision CHAIN span."""
    with trace_block("recovery_decision", "CHAIN") as span:
        set_attrs(span, **{"recovery.trigger": trigger, "recovery.options": options})
        yield _Recovery(span)


def log_event(message: str, **kwargs: Any) -> None:
    """Writes a structured log line inside the active span if neatlogs is enabled."""
    if not _enabled or neatlogs is None:
        return
    try:
        neatlogs.log(message, **kwargs)
    except Exception:
        return None
