"""Add communication resilience, intelligence, and incident capabilities."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260908_add_communication_resilience"
down_revision = "20260908_add_communication_product_capabilities"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Align notification status/priority check constraints with the extended
    # lifecycle (email opens/clicks/bounces) and the BULK priority.
    with op.batch_alter_table("communication_notifications") as batch:
        batch.drop_constraint("ck_communication_notification_status", type_="check")
        batch.create_check_constraint(
            "ck_communication_notification_status",
            "status IN ('created', 'queued', 'processing', 'accepted', 'submitted', 'sent', 'delivered', 'opened', 'clicked', 'bounced', 'complained', 'failed', 'rejected', 'expired', 'cancelled', 'retrying', 'dead_letter')",
        )
        batch.drop_constraint("ck_communication_notification_priority", type_="check")
        batch.create_check_constraint(
            "ck_communication_notification_priority",
            "priority IN ('critical', 'high', 'normal', 'low', 'bulk')",
        )

    op.add_column("communication_notifications", sa.Column("queued_at", sa.DateTime(timezone=True)))
    op.add_column("communication_notifications", sa.Column("submitted_at", sa.DateTime(timezone=True)))
    op.add_column("communication_notifications", sa.Column("delivered_at", sa.DateTime(timezone=True)))
    op.add_column("communication_notifications", sa.Column("failed_at", sa.DateTime(timezone=True)))

    op.add_column("communication_attempts", sa.Column("error_category", sa.String(length=64)))
    op.add_column("communication_attempts", sa.Column("latency_ms", sa.Integer()))
    op.add_column("communication_attempts", sa.Column("cost", sa.JSON()))

    with op.batch_alter_table("communication_webhook_events") as batch:
        batch.alter_column("tenant_id", existing_type=sa.String(length=128), nullable=True)
        batch.add_column(sa.Column("payload_hash", sa.String(length=64)))
        batch.add_column(sa.Column("processing_status", sa.String(length=32), nullable=False, server_default="pending"))
        batch.add_column(sa.Column("signature_valid", sa.Integer(), server_default="1"))
        batch.create_index("ix_communication_webhook_processing_status", ["processing_status", "received_at"])

    with op.batch_alter_table("communication_otp_challenges") as batch:
        batch.add_column(sa.Column("ip_address", sa.String(length=64)))
        batch.add_column(sa.Column("context", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))

    op.create_table(
        "communication_incidents",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("reference", sa.String(length=32), nullable=False, unique=True),
        sa.Column("tenant_id", sa.String(length=128)),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False, server_default="medium"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="open"),
        sa.Column("fingerprint", sa.String(length=128), nullable=False),
        sa.Column("occurrence_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("affected_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("metrics", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("summary", sa.Text()),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True)),
        sa.Column("mitigated_at", sa.DateTime(timezone=True)),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("fingerprint", name="uq_communication_incident_fingerprint"),
    )
    op.create_index("ix_communication_incident_status_opened", "communication_incidents", ["status", "opened_at"])
    op.create_index("ix_communication_incident_tenant_opened", "communication_incidents", ["tenant_id", "opened_at"])

    op.create_table(
        "communication_saved_filters",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("owner_user_id", sa.String(length=128)),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("query", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "name", name="uq_communication_saved_filter_name"),
    )

    op.create_table(
        "communication_tenant_quotas",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("scope", sa.String(length=64), nullable=False),
        sa.Column("limit_value", sa.Integer(), nullable=False),
        sa.Column("window", sa.String(length=32), nullable=False, server_default="daily"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "scope", name="uq_communication_tenant_quota_scope"),
    )


def downgrade() -> None:
    op.drop_table("communication_tenant_quotas")
    op.drop_table("communication_saved_filters")
    op.drop_index("ix_communication_incident_tenant_opened", table_name="communication_incidents")
    op.drop_index("ix_communication_incident_status_opened", table_name="communication_incidents")
    op.drop_table("communication_incidents")

    with op.batch_alter_table("communication_campaigns") as batch:
        batch.drop_column("last_error")
        batch.drop_column("paused_at")
        batch.drop_column("failed_count")
        batch.drop_column("processed_count")
        batch.drop_column("rate_per_minute")

    with op.batch_alter_table("communication_otp_challenges") as batch:
        batch.drop_column("context")
        batch.drop_column("ip_address")

    with op.batch_alter_table("communication_webhook_events") as batch:
        batch.drop_index("ix_communication_webhook_processing_status")
        batch.drop_column("signature_valid")
        batch.drop_column("processing_status")
        batch.drop_column("payload_hash")

    op.drop_column("communication_attempts", "cost")
    op.drop_column("communication_attempts", "latency_ms")
    op.drop_column("communication_attempts", "error_category")

    with op.batch_alter_table("communication_notifications") as batch:
        batch.drop_constraint("ck_communication_notification_status", type_="check")
        batch.create_check_constraint(
            "ck_communication_notification_status",
            "status IN ('created', 'queued', 'processing', 'accepted', 'submitted', 'sent', 'delivered', 'failed', 'rejected', 'expired', 'cancelled', 'retrying', 'dead_letter')",
        )
        batch.drop_constraint("ck_communication_notification_priority", type_="check")
        batch.create_check_constraint(
            "ck_communication_notification_priority",
            "priority IN ('critical', 'high', 'normal', 'low')",
        )

    op.drop_column("communication_notifications", "failed_at")
    op.drop_column("communication_notifications", "delivered_at")
    op.drop_column("communication_notifications", "submitted_at")
    op.drop_column("communication_notifications", "queued_at")