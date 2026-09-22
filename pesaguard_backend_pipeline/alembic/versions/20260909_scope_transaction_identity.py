"""Scope transaction identity by tenant and provider account."""
from __future__ import annotations

from alembic import op
from alembic import context
import sqlalchemy as sa


revision = "20260909_scope_transaction_identity"
down_revision = "20260908_add_communication_resilience"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = None if context.is_offline_mode() else sa.inspect(op.get_bind())
    transactions_exist = context.is_offline_mode() or inspector.has_table("transactions")
    processed_transactions_exist = False if context.is_offline_mode() else inspector.has_table("processed_transactions")

    if transactions_exist:
        op.add_column("transactions", sa.Column("id", sa.String(), nullable=True))
        op.add_column("transactions", sa.Column("tenant_id", sa.String(), nullable=True))
        op.add_column("transactions", sa.Column("provider_account_id", sa.String(), nullable=True))
        op.execute(sa.text("UPDATE transactions SET id = md5(trans_id || ':' || COALESCE(tenant_id, 'default') || ':' || COALESCE(business_short_code, 'legacy-default')) WHERE id IS NULL"))
        op.execute(sa.text("UPDATE transactions SET tenant_id = COALESCE(tenant_id, 'default'), provider_account_id = COALESCE(NULLIF(business_short_code, ''), 'legacy-default')"))
        op.drop_constraint("transactions_pkey", "transactions", type_="primary")
        op.create_primary_key("transactions_pkey", "transactions", ["id"])
        op.drop_constraint("uq_transaction_trans_id", "transactions", type_="unique")
        op.alter_column("transactions", "id", nullable=False)
        op.alter_column("transactions", "tenant_id", nullable=False)
        op.alter_column("transactions", "provider_account_id", nullable=False)
        op.create_unique_constraint("uq_transaction_scope_trans_id", "transactions", ["tenant_id", "provider_account_id", "trans_id"])
        op.create_index("ix_transaction_scope_trans_id", "transactions", ["tenant_id", "provider_account_id", "trans_id"])

    if not processed_transactions_exist:
        op.create_table(
            "processed_transactions",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("daraja_trans_id", sa.String(), nullable=False),
            sa.Column("tenant_id", sa.String(), nullable=False, server_default="default"),
            sa.Column("provider_account_id", sa.String(), nullable=False, server_default="legacy-default"),
            sa.Column("status", sa.String(), nullable=False, server_default="received"),
            sa.Column("processing_time_ms", sa.Integer()),
            sa.Column("received_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("webhook_attempt_number", sa.Integer(), server_default="1"),
            sa.Column("source_ip", sa.String()),
            sa.Column("signature_verified", sa.Boolean(), server_default=sa.text("false")),
            sa.Column("error_reason", sa.String()),
            sa.UniqueConstraint("tenant_id", "provider_account_id", "daraja_trans_id", name="uq_processed_scope_trans_id"),
        )
    else:
        op.add_column("processed_transactions", sa.Column("provider_account_id", sa.String(), nullable=True))
        op.execute(sa.text("UPDATE processed_transactions SET provider_account_id = 'legacy-default' WHERE provider_account_id IS NULL"))
        op.alter_column("processed_transactions", "provider_account_id", nullable=False)
        op.drop_constraint("uq_daraja_trans_id", "processed_transactions", type_="unique")
        op.create_unique_constraint("uq_processed_scope_trans_id", "processed_transactions", ["tenant_id", "provider_account_id", "daraja_trans_id"])


def downgrade() -> None:
    raise RuntimeError("Transaction identity scoping is irreversible after data backfill")