"""Persist canonical reconciliation decision evidence."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260913_add_reconciliation_matches"
down_revision = "20260913_phase1_foreign_keys"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if sa.inspect(bind).has_table("reconciliation_matches"):
        return
    op.create_table(
        "reconciliation_matches",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("transaction_id", sa.String(), nullable=False),
        sa.Column("matched_record", sa.JSON(), nullable=True),
        sa.Column("matching_rules", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("match_score", sa.Numeric(5, 4), nullable=False),
        sa.Column("match_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("engine_version", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("processing_latency_ms", sa.Numeric(12, 3), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "transaction_id", name="uq_reconciliation_matches_transaction"),
        sa.CheckConstraint("tenant_id IS NOT NULL AND tenant_id <> ''", name="ck_reconciliation_matches_tenant_nonempty"),
        sa.CheckConstraint("status IN ('MATCHED', 'UNMATCHED', 'PARTIAL', 'MISMATCH', 'DUPLICATE', 'PENDING', 'EXCEPTION')", name="ck_reconciliation_matches_status"),
        sa.CheckConstraint("match_score >= 0 AND match_score <= 1", name="ck_reconciliation_matches_score"),
    )
    op.create_index(
        "ix_reconciliation_matches_tenant_status",
        "reconciliation_matches",
        ["tenant_id", "status", "created_at"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("reconciliation_matches"):
        return
    op.drop_index("ix_reconciliation_matches_tenant_status", table_name="reconciliation_matches")
    op.drop_table("reconciliation_matches")
