"""Forward repair for the existing 001 production deployment."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "002_repair_queue_schema"
down_revision = "001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    tables = inspector.get_table_names()
    if "payload" not in {column["name"] for column in inspector.get_columns("jobs")}:
        op.add_column("jobs", sa.Column("payload", sa.JSON(), nullable=False, server_default="{}"))
    if connection.dialect.name != "postgresql":
        if connection.dialect.name == "sqlite":
            convention = {"fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"}
            with op.batch_alter_table("application_events", naming_convention=convention) as batch:
                batch.drop_constraint("fk_application_events_application_id_applications", type_="foreignkey")
                batch.create_foreign_key("fk_application_events_application_id_applications", "applications",
                    ["application_id"], ["id"], ondelete="RESTRICT")
        return
    # Drop dependent foreign keys before casting UUID identifiers, then recreate.
    foreign_keys = [(table, fk) for table in tables for fk in inspector.get_foreign_keys(table)]
    for table, fk in foreign_keys:
        op.drop_constraint(fk["name"], table, type_="foreignkey")
    for table in tables:
        for column in inspector.get_columns(table):
            if column["name"] in {"id", "user_id", "scholarship_id", "application_id"} and not isinstance(column["type"], UUID):
                op.alter_column(table, column["name"], type_=UUID(as_uuid=True),
                    postgresql_using='"' + column["name"] + '"::uuid')
    for table, fk in foreign_keys:
        deletion = "RESTRICT" if table == "application_events" else fk.get("options", {}).get("ondelete")
        op.create_foreign_key(fk["name"], table, fk["referred_table"],
            fk["constrained_columns"], fk["referred_columns"], ondelete=deletion)


def downgrade() -> None:
    # UUID conversion is intentionally not reversed: deployment rollback needs a backup.
    raise RuntimeError("Restore a verified backup to roll back identifier conversion.")
