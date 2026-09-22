"""Reject zero-value financial transactions."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260913_require_positive_transaction_amounts"
down_revision = "20260913_add_webhook_delivery_tenant_scope"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    constraints = {
        constraint["name"]
        for constraint in inspector.get_check_constraints("transactions")
    }
    if "ck_transactions_trans_amount_nonnegative" in constraints:
        with op.batch_alter_table("transactions") as batch_op:
            batch_op.drop_constraint("ck_transactions_trans_amount_nonnegative", type_="check")
    if "ck_transactions_trans_amount_positive" not in constraints:
        with op.batch_alter_table("transactions") as batch_op:
            batch_op.create_check_constraint(
                "ck_transactions_trans_amount_positive",
                "trans_amount > 0",
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    constraints = {
        constraint["name"]
        for constraint in inspector.get_check_constraints("transactions")
    }
    if "ck_transactions_trans_amount_positive" in constraints:
        with op.batch_alter_table("transactions") as batch_op:
            batch_op.drop_constraint("ck_transactions_trans_amount_positive", type_="check")
    if "ck_transactions_trans_amount_nonnegative" not in constraints:
        with op.batch_alter_table("transactions") as batch_op:
            batch_op.create_check_constraint(
                "ck_transactions_trans_amount_nonnegative",
                "trans_amount >= 0",
            )
