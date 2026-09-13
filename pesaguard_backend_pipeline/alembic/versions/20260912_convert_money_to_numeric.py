"""Convert financial amounts from floating point to fixed precision numeric."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260912_convert_money_to_numeric"
down_revision = "20260912_add_reconciliation_state"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "transactions" in tables and "trans_amount" in {column["name"] for column in inspector.get_columns("transactions")}:
        op.alter_column(
            "transactions",
            "trans_amount",
            existing_type=sa.Float(),
            type_=sa.Numeric(18, 2),
            postgresql_using="round(trans_amount::numeric, 2)",
        )
        op.create_check_constraint("ck_transactions_trans_amount_nonnegative", "transactions", "trans_amount >= 0")
    if "internal_records" in tables and "amount" in {column["name"] for column in inspector.get_columns("internal_records")}:
        op.alter_column(
            "internal_records",
            "amount",
            existing_type=sa.Float(),
            type_=sa.Numeric(18, 2),
            postgresql_using="round(amount::numeric, 2)",
        )
        op.create_check_constraint("ck_internal_records_amount_nonnegative", "internal_records", "amount >= 0")


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "internal_records" in tables:
        op.drop_constraint("ck_internal_records_amount_nonnegative", "internal_records", type_="check")
        op.alter_column("internal_records", "amount", existing_type=sa.Numeric(18, 2), type_=sa.Float())
    if "transactions" in tables:
        op.drop_constraint("ck_transactions_trans_amount_nonnegative", "transactions", type_="check")
        op.alter_column("transactions", "trans_amount", existing_type=sa.Numeric(18, 2), type_=sa.Float())