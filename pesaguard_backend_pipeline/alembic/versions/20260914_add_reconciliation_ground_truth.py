"""Add validated ground-truth cases for reconciliation certification metrics."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260914_add_reconciliation_ground_truth"
down_revision = "20260913_add_reconciliation_matches"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if sa.inspect(bind).has_table("reconciliation_ground_truth"):
        return
    op.create_table(
        "reconciliation_ground_truth",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("transaction_id", sa.String(), nullable=False),
        sa.Column("expected_status", sa.String(32), nullable=False),
        sa.Column("actual_status", sa.String(32), nullable=True),
        sa.Column("source", sa.String(64), nullable=False, server_default="certification"),
        sa.Column("validated_by", sa.String(128), nullable=True),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "transaction_id", name="uq_reconciliation_ground_truth_transaction"),
        sa.CheckConstraint("tenant_id IS NOT NULL AND tenant_id <> ''", name="ck_reconciliation_ground_truth_tenant_nonempty"),
        sa.CheckConstraint("expected_status IN ('MATCHED', 'UNMATCHED', 'PARTIAL', 'MISMATCH', 'DUPLICATE', 'PENDING', 'EXCEPTION')", name="ck_ground_truth_expected_status"),
        sa.CheckConstraint("actual_status IS NULL OR actual_status IN ('MATCHED', 'UNMATCHED', 'PARTIAL', 'MISMATCH', 'DUPLICATE', 'PENDING', 'EXCEPTION')", name="ck_ground_truth_actual_status"),
    )
    op.create_index("ix_reconciliation_ground_truth_validation", "reconciliation_ground_truth", ["tenant_id", "validated_at"])


def downgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("reconciliation_ground_truth"):
        return
    op.drop_index("ix_reconciliation_ground_truth_validation", table_name="reconciliation_ground_truth")
    op.drop_table("reconciliation_ground_truth")
