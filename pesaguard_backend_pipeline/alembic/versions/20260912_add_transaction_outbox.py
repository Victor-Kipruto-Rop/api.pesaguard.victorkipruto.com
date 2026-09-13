"""Add durable transaction publication outbox."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260912_add_transaction_outbox"
down_revision = "20260912_harden_passwordless_challenges"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "transaction_outbox",
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
        sa.UniqueConstraint("tenant_id", "event_key", name="uq_transaction_outbox_tenant_event"),
    )
    op.create_index("ix_transaction_outbox_pending", "transaction_outbox", ["status", "available_at", "created_at"])
    op.create_index("ix_transaction_outbox_tenant_created", "transaction_outbox", ["tenant_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_transaction_outbox_tenant_created", table_name="transaction_outbox")
    op.drop_index("ix_transaction_outbox_pending", table_name="transaction_outbox")
    op.drop_table("transaction_outbox")