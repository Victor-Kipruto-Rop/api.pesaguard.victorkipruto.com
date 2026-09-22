"""Add controlled deletion request workflow state."""

from alembic import op
import sqlalchemy as sa


revision = "20260923_add_deletion_requests"
down_revision = "20260923_add_merchant_metrics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "deletion_requests",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("transaction_id", sa.String(), nullable=False),
        sa.Column("requested_by", sa.String(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("decision", sa.String(length=32)),
        sa.Column("dependency_report", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("authorization_reference", sa.String(length=255)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("tenant_id IS NOT NULL AND tenant_id <> ''", name="ck_deletion_request_tenant_nonempty"),
        sa.CheckConstraint("status IN ('pending', 'approved', 'anonymized', 'deleted', 'rejected', 'failed')", name="ck_deletion_request_status"),
    )
    op.create_index("ix_deletion_requests_tenant_status", "deletion_requests", ["tenant_id", "status", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_deletion_requests_tenant_status", table_name="deletion_requests")
    op.drop_table("deletion_requests")