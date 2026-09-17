"""Add append-only transaction and discrepancy lifecycle history."""

from alembic import op
import sqlalchemy as sa


revision = "20260913_add_immutable_financial_history"
down_revision = "20260913_harden_dead_letter_replay"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "transactions" in tables:
        columns = {column["name"] for column in inspector.get_columns("transactions")}
        if "currency" not in columns:
            op.add_column("transactions", sa.Column("currency", sa.String(3), nullable=True, server_default="KES"))
            op.execute(sa.text("UPDATE transactions SET currency = 'KES' WHERE currency IS NULL"))
            op.alter_column("transactions", "currency", nullable=False, server_default="KES")
        constraints = {constraint["name"] for constraint in inspector.get_check_constraints("transactions")}
        if "ck_transactions_trans_amount_nonnegative" not in constraints:
            op.create_check_constraint("ck_transactions_trans_amount_nonnegative", "transactions", "trans_amount >= 0")
        if "ck_transactions_currency_iso" not in constraints:
            op.create_check_constraint("ck_transactions_currency_iso", "transactions", "length(currency) = 3 AND currency = upper(currency)")

    if "transaction_events" not in tables:
        op.create_table(
            "transaction_events",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("tenant_id", sa.String(), nullable=False),
            sa.Column("transaction_id", sa.String(), nullable=True),
            sa.Column("trans_id", sa.String(), nullable=False),
            sa.Column("event_key", sa.String(), nullable=False),
            sa.Column("event_type", sa.String(), nullable=False),
            sa.Column("from_state", sa.String(), nullable=True),
            sa.Column("to_state", sa.String(), nullable=False),
            sa.Column("actor", sa.String(), nullable=False),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("payload_hash", sa.String(64), nullable=True),
            sa.Column("correlation_id", sa.String(), nullable=True),
            sa.Column("details", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("tenant_id", "event_key", name="uq_transaction_events_tenant_key"),
        )
        op.create_index("ix_transaction_events_transaction", "transaction_events", ["tenant_id", "transaction_id", "created_at"])
        op.create_index("ix_transaction_events_correlation", "transaction_events", ["tenant_id", "correlation_id"])

    if "discrepancy_events" not in tables:
        op.create_table(
            "discrepancy_events",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("tenant_id", sa.String(), nullable=False),
            sa.Column("discrepancy_id", sa.String(), nullable=False),
            sa.Column("event_key", sa.String(), nullable=False),
            sa.Column("from_state", sa.String(), nullable=True),
            sa.Column("to_state", sa.String(), nullable=False),
            sa.Column("actor", sa.String(), nullable=False),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("correlation_id", sa.String(), nullable=True),
            sa.Column("details", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("tenant_id", "event_key", name="uq_discrepancy_events_tenant_key"),
        )
        op.create_index("ix_discrepancy_events_scope", "discrepancy_events", ["tenant_id", "discrepancy_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_discrepancy_events_scope", table_name="discrepancy_events")
    op.drop_table("discrepancy_events")
    op.drop_index("ix_transaction_events_correlation", table_name="transaction_events")
    op.drop_index("ix_transaction_events_transaction", table_name="transaction_events")
    op.drop_table("transaction_events")
    op.drop_constraint("ck_transactions_currency_iso", "transactions", type_="check")
    op.drop_constraint("ck_transactions_trans_amount_nonnegative", "transactions", type_="check")
    op.drop_column("transactions", "currency")
