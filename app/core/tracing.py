"""Neatlogs tracing, span helpers, guardrail audits, and recovery decisions for root app."""
import functools
import inspect
from collections.abc import Callable, Generator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Optional
from app.core.config import settings
from backend.app.tracing import init_tracing as shared_init, shutdown_tracing as shared_shutdown

try:
    import neatlogs
except ImportError:
    neatlogs = None

_enabled: bool = False
_context: ContextVar[dict[str, Any]] = ContextVar("scholarpilot_trace_context", default={})


@contextmanager
def application_context(application_id: str, listing_id: str, mode: str) -> Generator[None, None, None]:
    token = _context.set({"application_id": application_id, "listing_id": listing_id, "mode": mode})
    try:
        yield
    finally:
        _context.reset(token)


def trace_identifier(span: Any) -> str | None:
    context = span.get_span_context() if hasattr(span, "get_span_context") else None
    return format(context.trace_id, "032x") if context and context.is_valid else None


def current_application_id() -> str | None:
    return _context.get().get("application_id")


def log_event(message: str, **kwargs: Any) -> None:
    if _enabled and neatlogs is not None:
        neatlogs.log(message, **kwargs)


class _NoSpan:
    """Fallback dummy span used when tracing is disabled."""
    def set_attribute(self, key: str, value: Any) -> None:
        return None


def init_tracing(tags: Optional[list[str]] = None) -> bool:
    """Initializes neatlogs tracing once per process."""
    global _enabled
    if _enabled:
        return True
    if neatlogs is None or not settings.NEATLOGS_API_KEY:
        return False

    try:
        _enabled = shared_init(tags=tags)
        return _enabled
    except Exception:
        return False


def shutdown_tracing() -> None:
    """Flushes and shuts down neatlogs tracing at server or process exit."""
    global _enabled
    if _enabled and neatlogs is not None:
        try:
            shared_shutdown()
        except Exception:
            pass
        _enabled = False


def tracing_enabled() -> bool:
    """Returns True if neatlogs tracing is active."""
    return _enabled


def get_trace_url(run_id: Optional[str] = None) -> Optional[str]:
    """Return no deep link until the SDK supplies a verified dashboard trace ID."""
    return None


def _clean(value: Any) -> Any:
    """Cleans an attribute value for span metadata."""
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

        if inspect.iscoroutinefunction(fn):
            @functools.wraps(fn)
            async def async_inner(*args: Any, **kw: Any) -> Any:
                with trace_block(name, kind, **extra, **{"code.filepath": fn.__code__.co_filename,
                    "code.function": fn.__name__, "code.lineno": fn.__code__.co_firstlineno}):
                    return await fn(*args, **kw)
            return async_inner
        return inner

    return decorator


def workflow_span(name: str) -> Callable:
    """Decorates a workflow entry point with kind WORKFLOW."""
    return _lazy_span("WORKFLOW", name)


def agent_span(name: str, role: Optional[str] = None, goal: Optional[str] = None) -> Callable:
    """Decorates an agent function with kind AGENT."""
    extra: dict[str, Any] = {}
    if role:
        extra["role"] = role
    if goal:
        extra["goal"] = goal
    return _lazy_span("AGENT", "agent_" + name, **extra)


def tool_span(tool_name: str, description: Optional[str] = None) -> Callable:
    """Decorates a tool invocation with kind TOOL."""
    extra: dict[str, Any] = {"tool_name": tool_name}
    if description:
        extra["description"] = description
    return _lazy_span("TOOL", tool_name, **extra)


@contextmanager
def trace_block(name: str, kind: str, **attrs: Any) -> Generator[Any, None, None]:
    """Context manager opening an inline trace span."""
    if not _enabled or neatlogs is None:
        yield _NoSpan()
        return
    try:
        with neatlogs.trace(name, kind=kind) as span:
            set_attrs(span, **{**_context.get(), **attrs})
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
            self.span.set_attribute("neatlogs.guardrail.input", f"characters={len(str(input_text))}")
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


class _Recovery:
    """Helper wrapper for recovery_decision spans."""
    def __init__(self, span: Any) -> None:
        self.span = span

    def decide(self, chosen: str, reason: str) -> None:
        set_attrs(self.span, **{"recovery.chosen": chosen, "recovery.reason": reason})
        log_event("Recovery selected", chosen=chosen, reason=reason)

    def finish(self, outcome: str) -> None:
        set_attrs(self.span, **{"recovery.outcome": outcome})


@contextmanager
def recovery_decision(trigger: str, options: list[str]) -> Generator[_Recovery, None, None]:
    """Context manager opening a recovery_decision CHAIN span."""
    with trace_block("recovery_decision", "CHAIN") as span:
        set_attrs(span, **{"recovery.trigger": trigger, "recovery.options": options})
        yield _Recovery(span)
