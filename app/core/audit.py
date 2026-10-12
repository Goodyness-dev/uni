"""Database guards for workflow audit rows with an explicit privacy exception."""
from uuid import UUID
from sqlalchemy import event, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.base import Base, engine

POSTGRES_GUARD = """
CREATE OR REPLACE FUNCTION scholarpilot_guard_event() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'DELETE' AND EXISTS (
    SELECT 1 FROM applications WHERE id = OLD.application_id
    AND user_id::text = current_setting('scholarpilot.erasure_owner', true)
  ) THEN RETURN OLD; END IF;
  RAISE EXCEPTION 'Audit events are append-only outside governed privacy erasure';
END $$;
"""


def install_sqlite_functions(connection: object, record: object) -> None:
    if engine.dialect.name != "sqlite":
        return
    state = {"owner": ""}
    def set_owner(value: str) -> int:
        state["owner"] = value
        return 1
    connection.create_function("scholarpilot_erasure_owner", 0, lambda: state["owner"])
    connection.create_function("scholarpilot_set_erasure_owner", 1, set_owner)
    record.info["audit_state"] = state


def clear_sqlite_owner(connection: object, record: object) -> None:
    if "audit_state" in record.info:
        record.info["audit_state"]["owner"] = ""


def create_audit_guards(connection: Connection) -> None:
    if connection.dialect.name == "postgresql":
        connection.execute(text(POSTGRES_GUARD))
        connection.execute(text("DROP TRIGGER IF EXISTS scholarpilot_event_guard ON application_events"))
        connection.execute(text("CREATE TRIGGER scholarpilot_event_guard BEFORE UPDATE OR DELETE ON application_events FOR EACH ROW EXECUTE FUNCTION scholarpilot_guard_event()"))
    elif connection.dialect.name == "sqlite":
        connection.execute(text("CREATE TRIGGER IF NOT EXISTS scholarpilot_event_update BEFORE UPDATE ON application_events BEGIN SELECT RAISE(ABORT, 'Audit events cannot be updated'); END"))
        connection.execute(text("CREATE TRIGGER IF NOT EXISTS scholarpilot_event_delete BEFORE DELETE ON application_events WHEN NOT EXISTS (SELECT 1 FROM applications WHERE id=OLD.application_id AND user_id=scholarpilot_erasure_owner()) BEGIN SELECT RAISE(ABORT, 'Audit events cannot be deleted outside privacy erasure'); END"))


async def authorize_privacy_erasure(session: AsyncSession, owner: UUID) -> None:
    if session.get_bind().dialect.name == "postgresql":
        await session.execute(text("SELECT set_config('scholarpilot.erasure_owner', :owner, true)"), {"owner": str(owner)})
    else:
        await session.execute(text("SELECT scholarpilot_set_erasure_owner(:owner)"), {"owner": str(owner)})


def metadata_guards(metadata: object, connection: Connection, **kwargs: object) -> None:
    create_audit_guards(connection)


event.listen(engine.sync_engine, "connect", install_sqlite_functions)
event.listen(engine.sync_engine, "checkin", clear_sqlite_owner)
event.listen(Base.metadata, "after_create", metadata_guards)
