"""Append-only audit guards with owner-scoped privacy erasure."""
from alembic import op
from app.core.audit import create_audit_guards

revision = "003_audit_guards"
down_revision = "002_repair_queue_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    create_audit_guards(op.get_bind())


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS scholarpilot_event_guard ON application_events")
        op.execute("DROP FUNCTION IF EXISTS scholarpilot_guard_event()")
    else:
        op.execute("DROP TRIGGER IF EXISTS scholarpilot_event_update")
        op.execute("DROP TRIGGER IF EXISTS scholarpilot_event_delete")
