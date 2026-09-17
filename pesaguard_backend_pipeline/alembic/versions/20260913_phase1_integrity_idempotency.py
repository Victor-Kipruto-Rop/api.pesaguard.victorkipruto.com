"""Add phase-one transaction identity, idempotency, and immutable audit ledgers."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260913_phase1_integrity_idempotency"
down_revision = "20260913_require_positive_transaction_amounts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "transactions" in tables:
        columns = {column["name"] for column in inspector.get_columns("transactions")}
        additions = (
            ("provider", sa.String(64), "mpesa"),
            ("idempotency_key", sa.String(255), None),
            ("external_reference", sa.String(255), None),
            ("provider_transaction_id", sa.String(255), None),
            ("status", sa.String(32), "RECEIVED"),
            ("version", sa.Integer(), "1"),
        )
        for name, column_type, default in additions:
            if name not in columns:
                with op.batch_alter_table("transactions") as batch:
                    batch.add_column(sa.Column(name, column_type, nullable=True, server_default=default))
        op.execute(sa.text("UPDATE transactions SET provider = 'mpesa' WHERE provider IS NULL"))
        op.execute(sa.text("UPDATE transactions SET provider_transaction_id = trans_id WHERE provider_transaction_id IS NULL"))
        op.execute(sa.text("UPDATE transactions SET idempotency_key = 'transid:' || upper(trans_id) WHERE idempotency_key IS NULL"))
        op.execute(sa.text("UPDATE transactions SET status = 'RECEIVED' WHERE status IS NULL"))
        op.execute(sa.text("UPDATE transactions SET version = 1 WHERE version IS NULL"))
        with op.batch_alter_table("transactions") as batch:
            for name in ("provider", "idempotency_key", "provider_transaction_id", "status", "version"):
                batch.alter_column(name, nullable=False)
            existing = {constraint["name"] for constraint in inspector.get_unique_constraints("transactions")}
            if "uq_transaction_provider_reference" not in existing:
                batch.create_unique_constraint("uq_transaction_provider_reference", ["tenant_id", "provider", "provider_transaction_id"])
            if "uq_transaction_external_reference" not in existing:
                batch.create_unique_constraint("uq_transaction_external_reference", ["tenant_id", "provider", "external_reference"])
            batch.create_check_constraint("ck_transactions_status", "status IN ('RECEIVED', 'VALIDATED', 'PROCESSING', 'RECONCILING', 'RECONCILED', 'FAILED', 'REJECTED')")
            batch.create_check_constraint("ck_transactions_version_positive", "version >= 1")
            batch.alter_column("tenant_id", server_default=None)
        if "processed_transactions" in tables:
            with op.batch_alter_table("processed_transactions") as batch:
                batch.alter_column("tenant_id", server_default=None)

    if "idempotency_records" not in tables:
        op.create_table(
            "idempotency_records",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("tenant_id", sa.String(), nullable=False),
            sa.Column("provider", sa.String(64), nullable=False),
            sa.Column("idempotency_key", sa.String(255), nullable=False),
            sa.Column("external_reference", sa.String(255), nullable=True),
            sa.Column("provider_transaction_id", sa.String(255), nullable=False),
            sa.Column("request_hash", sa.String(64), nullable=False),
            sa.Column("response", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("tenant_id", "provider", "idempotency_key", name="uq_idempotency_request"),
            sa.UniqueConstraint("tenant_id", "provider", "provider_transaction_id", name="uq_idempotency_provider_reference"),
            sa.CheckConstraint("tenant_id IS NOT NULL AND tenant_id <> ''", name="ck_idempotency_tenant_id_nonempty"),
        )
        op.create_index("ix_idempotency_tenant_key", "idempotency_records", ["tenant_id", "idempotency_key"])

    if "audit_events" not in tables:
        op.create_table(
            "audit_events",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("tenant_id", sa.String(), nullable=False),
            sa.Column("event_key", sa.String(), nullable=False),
            sa.Column("event_type", sa.String(), nullable=False),
            sa.Column("aggregate_type", sa.String(), nullable=False),
            sa.Column("aggregate_id", sa.String(), nullable=False),
            sa.Column("actor", sa.String(), nullable=False),
            sa.Column("payload_hash", sa.String(64), nullable=False),
            sa.Column("details", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("tenant_id", "event_key", name="uq_audit_events_tenant_key"),
            sa.CheckConstraint("tenant_id IS NOT NULL AND tenant_id <> ''", name="ck_audit_events_tenant_id_nonempty"),
        )
        op.create_index("ix_audit_events_tenant_created", "audit_events", ["tenant_id", "created_at"])

    if bind.dialect.name == "postgresql":
        op.execute(sa.text("""
            CREATE OR REPLACE FUNCTION reject_financial_history_mutation()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                RAISE EXCEPTION 'financial history is append-only';
            END;
            $$
        """))
        op.execute(sa.text("""
            CREATE TRIGGER transaction_events_append_only
            BEFORE UPDATE OR DELETE ON transaction_events
            FOR EACH ROW EXECUTE FUNCTION reject_financial_history_mutation()
        """))
        op.execute(sa.text("""
            CREATE TRIGGER audit_events_append_only
            BEFORE UPDATE OR DELETE ON audit_events
            FOR EACH ROW EXECUTE FUNCTION reject_financial_history_mutation()
        """))
        op.execute(sa.text("REVOKE UPDATE, DELETE, TRUNCATE ON transaction_events, audit_events FROM PUBLIC"))


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(sa.text("DROP TRIGGER IF EXISTS audit_events_append_only ON audit_events"))
        op.execute(sa.text("DROP TRIGGER IF EXISTS transaction_events_append_only ON transaction_events"))
        op.execute(sa.text("DROP FUNCTION IF EXISTS reject_financial_history_mutation()"))
    op.drop_index("ix_audit_events_tenant_created", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index("ix_idempotency_tenant_key", table_name="idempotency_records")
    op.drop_table("idempotency_records")
    with op.batch_alter_table("transactions") as batch:
        batch.drop_constraint("ck_transactions_version_positive", type_="check")
        batch.drop_constraint("ck_transactions_status", type_="check")
        batch.drop_constraint("uq_transaction_external_reference", type_="unique")
        batch.drop_constraint("uq_transaction_provider_reference", type_="unique")
        for name in ("version", "status", "provider_transaction_id", "external_reference", "idempotency_key", "provider"):
            batch.drop_column(name)
