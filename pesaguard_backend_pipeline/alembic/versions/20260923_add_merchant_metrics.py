"""Add persisted merchant aggregation buckets."""

from alembic import op
import sqlalchemy as sa


revision = "20260923_add_merchant_metrics"
down_revision = "20260923_add_transformation_records"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "merchant_metrics",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("merchant_id", sa.String(), nullable=False),
        sa.Column("granularity", sa.String(length=8), nullable=False),
        sa.Column("bucket_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("transaction_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_volume", sa.Numeric(20, 2), nullable=False, server_default="0"),
        sa.Column("average_transaction", sa.Numeric(20, 2), nullable=False, server_default="0"),
        sa.Column("failed_transactions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reconciled_transactions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("anomaly_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "merchant_id", "granularity", "bucket_start", name="uq_merchant_metric_bucket"),
        sa.CheckConstraint("tenant_id IS NOT NULL AND tenant_id <> ''", name="ck_merchant_metrics_tenant_nonempty"),
        sa.CheckConstraint("granularity IN ('hour', 'day', 'week')", name="ck_merchant_metrics_granularity"),
    )
    op.create_index("ix_merchant_metrics_tenant_bucket", "merchant_metrics", ["tenant_id", "granularity", "bucket_start"])


def downgrade() -> None:
    op.drop_index("ix_merchant_metrics_tenant_bucket", table_name="merchant_metrics")
    op.drop_table("merchant_metrics")