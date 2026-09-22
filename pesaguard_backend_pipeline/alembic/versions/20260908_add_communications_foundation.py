"""Add communications notification and delivery foundation tables."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260908_add_communications_foundation"
down_revision = "20260908_harden_audit_integrity_controls"
branch_labels = None
depends_on = None


_NOTIFICATION_STATUSES = "'created', 'queued', 'processing', 'accepted', 'submitted', 'sent', 'delivered', 'failed', 'rejected', 'expired', 'cancelled', 'retrying', 'dead_letter'"


def upgrade() -> None:
    op.create_table(
        "communication_notifications",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("recipient", sa.String(length=255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("template_id", sa.String(length=128), nullable=True),
        sa.Column("priority", sa.String(length=16), nullable=False, server_default="normal"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="created"),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=True),
        sa.Column("provider_message_id", sa.String(length=255), nullable=True),
        sa.Column("correlation_id", sa.String(length=128), nullable=True),
        sa.Column("trace_id", sa.String(length=128), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("failure_code", sa.String(length=64), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="uq_communication_notification_idempotency"),
        sa.CheckConstraint(f"status IN ({_NOTIFICATION_STATUSES})", name="ck_communication_notification_status"),
        sa.CheckConstraint("priority IN ('critical', 'high', 'normal', 'low')", name="ck_communication_notification_priority"),
    )
    op.create_index(
        "ix_communication_notification_tenant_status_created",
        "communication_notifications",
        ["tenant_id", "status", "created_at"],
    )
    op.create_index(
        "ix_communication_notification_tenant_correlation",
        "communication_notifications",
        ["tenant_id", "correlation_id"],
    )

    op.create_table(
        "communication_attempts",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("notification_id", sa.String(length=64), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("provider_message_id", sa.String(length=255), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("notification_id", "attempt_number", name="uq_communication_attempt_number"),
        sa.ForeignKeyConstraint(["notification_id"], ["communication_notifications.id"], name="fk_communication_attempt_notification"),
    )
    op.create_index(
        "ix_communication_attempt_notification_started",
        "communication_attempts",
        ["notification_id", "started_at"],
    )

    op.create_table(
        "communication_delivery_reports",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("notification_id", sa.String(length=64), nullable=True),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("provider_event_id", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "provider_event_id", name="uq_communication_delivery_provider_event"),
        sa.ForeignKeyConstraint(["notification_id"], ["communication_notifications.id"], name="fk_communication_delivery_notification"),
    )
    op.create_index(
        "ix_communication_delivery_notification_received",
        "communication_delivery_reports",
        ["notification_id", "received_at"],
    )
    op.create_index(
        "ix_communication_delivery_tenant_status_received",
        "communication_delivery_reports",
        ["tenant_id", "status", "received_at"],
    )

    op.create_table(
        "communication_webhook_events",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("provider_event_id", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="received"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "provider_event_id", "event_type", name="uq_communication_webhook_event"),
    )
    op.create_index(
        "ix_communication_webhook_tenant_received",
        "communication_webhook_events",
        ["tenant_id", "received_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_communication_webhook_tenant_received", table_name="communication_webhook_events")
    op.drop_table("communication_webhook_events")
    op.drop_index("ix_communication_delivery_tenant_status_received", table_name="communication_delivery_reports")
    op.drop_index("ix_communication_delivery_notification_received", table_name="communication_delivery_reports")
    op.drop_table("communication_delivery_reports")
    op.drop_index("ix_communication_attempt_notification_started", table_name="communication_attempts")
    op.drop_table("communication_attempts")
    op.drop_index("ix_communication_notification_tenant_correlation", table_name="communication_notifications")
    op.drop_index("ix_communication_notification_tenant_status_created", table_name="communication_notifications")
    op.drop_table("communication_notifications")
