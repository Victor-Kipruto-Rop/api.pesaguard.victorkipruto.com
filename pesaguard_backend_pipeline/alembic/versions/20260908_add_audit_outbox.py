"""Add audit idempotency and durable outbox delivery state."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260908_add_audit_outbox"
down_revision = "20260908_add_structured_audit_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "action_audit_entries",
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
    )
    for name, length in (
        ("previous_hash", 64),
        ("event_hash", 64),
        ("signature", 256),
        ("signature_key_id", 128),
        ("signature_algorithm", 32),
    ):
        op.add_column("action_audit_entries", sa.Column(name, sa.String(length=length), nullable=True))
    with op.batch_alter_table("action_audit_entries") as batch_op:
        batch_op.create_unique_constraint(
            "uq_audit_tenant_idempotency_key",
            ["tenant_id", "idempotency_key"],
        )
    op.create_index("ix_audit_tenant_event_hash", "action_audit_entries", ["tenant_id", "event_hash"])
    op.create_table(
        "audit_outbox_entries",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("audit_id", sa.String(length=37), nullable=False),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["audit_id"], ["action_audit_entries.id"]),
        sa.UniqueConstraint("audit_id", name="uq_audit_outbox_audit_id"),
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="uq_audit_outbox_tenant_idempotency_key"),
    )
    op.create_index("ix_audit_outbox_due", "audit_outbox_entries", ["status", "next_attempt_at"])
    op.create_index(
        "ix_audit_outbox_tenant_status_created_at",
        "audit_outbox_entries",
        ["tenant_id", "status", "created_at"],
    )
    op.create_index(
        "ix_audit_outbox_tenant_delivered_at",
        "audit_outbox_entries",
        ["tenant_id", "delivered_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_audit_outbox_tenant_delivered_at", table_name="audit_outbox_entries")
    op.drop_index("ix_audit_outbox_tenant_status_created_at", table_name="audit_outbox_entries")
    op.drop_index("ix_audit_outbox_due", table_name="audit_outbox_entries")
    op.drop_table("audit_outbox_entries")
    op.drop_index("ix_audit_tenant_event_hash", table_name="action_audit_entries")
    with op.batch_alter_table("action_audit_entries") as batch_op:
        batch_op.drop_constraint("uq_audit_tenant_idempotency_key", type_="unique")
    for name in ("signature_algorithm", "signature_key_id", "signature", "event_hash", "previous_hash"):
        op.drop_column("action_audit_entries", name)
    op.drop_column("action_audit_entries", "idempotency_key")