"""Add append-only transaction data lineage records."""

from alembic import op
import sqlalchemy as sa


revision = "20260923_add_lineage_records"
down_revision = "20260923_add_deletion_requests"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lineage_records",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("transaction_id", sa.String(), nullable=False),
        sa.Column("event_id", sa.String(), nullable=False),
        sa.Column("stage", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("source_event_id", sa.String(length=255)),
        sa.Column("upstream_event_id", sa.String(length=255)),
        sa.Column("ingestion_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("pipeline_version", sa.String(length=64), nullable=False),
        sa.Column("transformation_version", sa.String(length=64), nullable=False),
        sa.Column("job_id", sa.String(length=255)),
        sa.Column("correlation_id", sa.String(length=255)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "event_id", "stage", name="uq_lineage_event_stage"),
        sa.CheckConstraint("tenant_id IS NOT NULL AND tenant_id <> ''", name="ck_lineage_tenant_nonempty"),
    )
    op.create_index("ix_lineage_tenant_transaction", "lineage_records", ["tenant_id", "transaction_id", "created_at"])
    op.create_index("ix_lineage_tenant_source_event", "lineage_records", ["tenant_id", "source_event_id"])


def downgrade() -> None:
    op.drop_index("ix_lineage_tenant_source_event", table_name="lineage_records")
    op.drop_index("ix_lineage_tenant_transaction", table_name="lineage_records")
    op.drop_table("lineage_records")