"""Add durable communications outbox leasing and retry state."""
from alembic import op
import sqlalchemy as sa

revision = "20260908_add_communication_outbox"
down_revision = "20260908_add_communications_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "communication_outbox_entries",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("notification_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("leased_by", sa.String(length=128), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["notification_id"], ["communication_notifications.id"], name="fk_communication_outbox_notification"),
        sa.UniqueConstraint("notification_id", name="uq_communication_outbox_notification"),
        sa.CheckConstraint("status IN ('pending', 'leased', 'retrying', 'completed', 'dead_letter')", name="ck_communication_outbox_status"),
        sa.CheckConstraint("attempt_count >= 0 AND max_attempts > 0", name="ck_communication_outbox_attempt_counts"),
    )
    op.create_index("ix_communication_outbox_due", "communication_outbox_entries", ["status", "available_at"])
    op.create_index("ix_communication_outbox_lease", "communication_outbox_entries", ["lease_expires_at"])
    op.create_index("ix_communication_outbox_tenant_status", "communication_outbox_entries", ["tenant_id", "status", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_communication_outbox_tenant_status", table_name="communication_outbox_entries")
    op.drop_index("ix_communication_outbox_lease", table_name="communication_outbox_entries")
    op.drop_index("ix_communication_outbox_due", table_name="communication_outbox_entries")
    op.drop_table("communication_outbox_entries")