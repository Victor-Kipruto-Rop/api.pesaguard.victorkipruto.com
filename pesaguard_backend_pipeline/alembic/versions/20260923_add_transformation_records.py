"""Add append-only transaction transformation evidence."""

from alembic import op
import sqlalchemy as sa


revision = "20260923_add_transformation_records"
down_revision = "20260923_add_import_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "transformation_records",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("transaction_id", sa.String(), nullable=False),
        sa.Column("event_id", sa.String(), nullable=False),
        sa.Column("source_event_id", sa.String(), nullable=True),
        sa.Column("stage", sa.String(length=16), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "event_id", "stage", name="uq_transformation_stage_event"),
        sa.CheckConstraint("tenant_id IS NOT NULL AND tenant_id <> ''", name="ck_transformation_tenant_nonempty"),
        sa.CheckConstraint("stage IN ('RAW', 'VALIDATED', 'NORMALIZED', 'ENRICHED', 'PROCESSED')", name="ck_transformation_stage"),
    )
    op.create_index("ix_transformation_tenant_transaction", "transformation_records", ["tenant_id", "transaction_id", "created_at"])
    op.create_index("ix_transformation_tenant_stage", "transformation_records", ["tenant_id", "stage", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_transformation_tenant_stage", table_name="transformation_records")
    op.drop_index("ix_transformation_tenant_transaction", table_name="transformation_records")
    op.drop_table("transformation_records")