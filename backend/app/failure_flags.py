from app.db import get_flags, set_flag, consume_flag, add_event
from app.errors import RunContext


def flag_active(name: str) -> bool:
    """Checks whether a failure flag is currently active."""
    flags_data = get_flags()
    return bool(flags_data["flags"].get(name, False))


def consume(name: str, ctx: RunContext | None = None) -> bool:
    """Consumes one use of a flag and logs the event if active."""
    active = consume_flag(name)
    if active and ctx and ctx.run_id:
        add_event(
            ctx.run_id,
            ctx.application_id,
            "coordinator",
            "failure_injected",
            f"Failure injected: {name}",
            {"flag": name},
        )
    return active
