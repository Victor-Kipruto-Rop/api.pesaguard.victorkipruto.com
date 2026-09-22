"""Separate ingestion state from reconciliation and result publication state."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260912_add_reconciliation_state"
down_revision = "20260912_add_transaction_outbox"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("processed_transactions", sa.Column("reconciliation_status", sa.String(), nullable=False, server_default="pending"))
    op.add_column("processed_transactions", sa.Column("reconciliation_attempts", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("processed_transactions", sa.Column("reconciliation_started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("processed_transactions", sa.Column("reconciliation_completed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("processed_transactions", sa.Column("reconciliation_error", sa.Text(), nullable=True))
    op.create_table(
        "reconciliation_outbox",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False, server_default="default"),
        sa.Column("event_key", sa.String(), nullable=False),
        sa.Column("topic", sa.String(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "event_key", name="uq_reconciliation_outbox_tenant_event"),
    )
    op.create_index("ix_reconciliation_outbox_pending", "reconciliation_outbox", ["status", "available_at", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_reconciliation_outbox_pending", table_name="reconciliation_outbox")
    op.drop_table("reconciliation_outbox")
    for column in ("reconciliation_error", "reconciliation_completed_at", "reconciliation_started_at", "reconciliation_attempts", "reconciliation_status"):
        op.drop_column("processed_transactions", column)