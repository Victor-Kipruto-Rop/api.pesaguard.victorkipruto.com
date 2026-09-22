"""Add tenant-scoped batch import job tracking."""

from alembic import op
import sqlalchemy as sa


revision = "20260923_add_import_jobs"
down_revision = "20260917_add_webhook_delivery_tenant_webhook_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "import_jobs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("file_format", sa.String(length=16), nullable=False),
        sa.Column("object_key", sa.String(length=512), nullable=False, unique=True),
        sa.Column("records_received", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_valid", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="queued"),
        sa.Column("error_summary", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("tenant_id IS NOT NULL AND tenant_id <> ''", name="ck_import_jobs_tenant_id_nonempty"),
        sa.CheckConstraint("status IN ('queued', 'running', 'completed', 'failed')", name="ck_import_jobs_status"),
        sa.CheckConstraint("records_received >= 0", name="ck_import_jobs_received_nonnegative"),
        sa.CheckConstraint("records_valid >= 0", name="ck_import_jobs_valid_nonnegative"),
        sa.CheckConstraint("records_failed >= 0", name="ck_import_jobs_failed_nonnegative"),
    )
    op.create_index("ix_import_jobs_tenant_status", "import_jobs", ["tenant_id", "status", "created_at"])
    op.create_index("ix_import_jobs_status_created", "import_jobs", ["status", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_import_jobs_status_created", table_name="import_jobs")
    op.drop_index("ix_import_jobs_tenant_status", table_name="import_jobs")
    op.drop_table("import_jobs")