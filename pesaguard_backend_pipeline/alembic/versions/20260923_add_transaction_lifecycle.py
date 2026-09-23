"""Add durable transaction lifecycle and archive markers."""

from alembic import op
import sqlalchemy as sa


revision = "20260923_add_transaction_lifecycle"
down_revision = ("20260923_merge_fraud_and_lineage_heads", "20260923_add_import_jobs")
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("transactions") as batch:
        batch.add_column(sa.Column("lifecycle_stage", sa.String(length=16), nullable=False, server_default="STORED"))
        batch.add_column(sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("archive_object_key", sa.String(length=1024), nullable=True))
        batch.create_check_constraint(
            "ck_transactions_lifecycle_stage",
            "lifecycle_stage IN ('CREATED', 'INGESTED', 'VALIDATED', 'PROCESSED', 'STORED', 'CONSUMED', 'ARCHIVED', 'DELETED', 'QUARANTINED')",
        )
        batch.create_index("ix_transactions_archived_at", ["archived_at"])


def downgrade() -> None:
    with op.batch_alter_table("transactions") as batch:
        batch.drop_index("ix_transactions_archived_at")
        batch.drop_constraint("ck_transactions_lifecycle_stage", type_="check")
        batch.drop_column("archive_object_key")
        batch.drop_column("archived_at")
        batch.drop_column("lifecycle_stage")