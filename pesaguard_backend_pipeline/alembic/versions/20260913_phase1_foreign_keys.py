"""Add Phase-1 foreign-key integrity constraints for financial event history.

Adds a tenant-scoped referential link from transaction_events.(tenant_id,
transaction_id) to transactions.(tenant_id, id), preventing deletion of referenced financial records.
even when a transaction is hard-deleted (which itself should never happen
in production since the ledger is append-only).

Revision ID: 20260913_phase1_foreign_keys
Revises: 20260913_phase1_integrity_idempotency
Create Date: 2026-09-13
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260913_phase1_foreign_keys"
down_revision = "20260913_phase1_integrity_idempotency"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "transaction_events" not in tables or "transactions" not in tables:
        return

    existing_uniques = {
        constraint["name"]
        for constraint in inspector.get_unique_constraints("transactions")
    }
    if "uq_transaction_tenant_id" not in existing_uniques:
        with op.batch_alter_table("transactions") as batch_op:
            batch_op.create_unique_constraint("uq_transaction_tenant_id", ["tenant_id", "id"])

    existing_fks = {
        constraint["name"]
        for constraint in inspector.get_foreign_keys("transaction_events")
    }

    if "fk_transaction_events_transaction_id" not in existing_fks:
        with op.batch_alter_table("transaction_events") as batch_op:
            batch_op.create_foreign_key(
                "fk_transaction_events_transaction_id",
                "transactions",
                ["tenant_id", "transaction_id"],
                ["tenant_id", "id"],
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "transaction_events" not in tables:
        return

    existing_fks = {
        constraint["name"]
        for constraint in inspector.get_foreign_keys("transaction_events")
    }
    if "fk_transaction_events_transaction_id" in existing_fks:
        with op.batch_alter_table("transaction_events") as batch_op:
            batch_op.drop_constraint("fk_transaction_events_transaction_id", type_="foreignkey")
    existing_uniques = {
        constraint["name"]
        for constraint in inspector.get_unique_constraints("transactions")
    }
    if "uq_transaction_tenant_id" in existing_uniques:
        with op.batch_alter_table("transactions") as batch_op:
            batch_op.drop_constraint("uq_transaction_tenant_id", type_="unique")