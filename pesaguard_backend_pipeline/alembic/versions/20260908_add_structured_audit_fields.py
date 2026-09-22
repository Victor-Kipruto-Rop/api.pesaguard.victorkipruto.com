"""Add structured enterprise fields to action audit entries."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260908_add_structured_audit_fields"
down_revision = "20260908_make_action_audit_append_only"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "action_audit_entries",
        sa.Column("category", sa.String(length=64), nullable=False, server_default="operations"),
    )
    op.add_column(
        "action_audit_entries",
        sa.Column("outcome", sa.String(length=32), nullable=False, server_default="success"),
    )
    op.add_column(
        "action_audit_entries",
        sa.Column("severity", sa.String(length=32), nullable=False, server_default="info"),
    )
    for name, length in (
        ("resource_type", 128),
        ("resource_id", 255),
        ("request_id", 128),
        ("trace_id", 128),
        ("correlation_id", 128),
    ):
        op.add_column("action_audit_entries", sa.Column(name, sa.String(length=length), nullable=True))

    op.create_index(
        "ix_audit_tenant_category_created_at",
        "action_audit_entries",
        ["tenant_id", "category", "created_at"],
    )
    op.create_index(
        "ix_audit_tenant_outcome_severity_created_at",
        "action_audit_entries",
        ["tenant_id", "outcome", "severity", "created_at"],
    )
    op.create_index(
        "ix_audit_tenant_resource_created_at",
        "action_audit_entries",
        ["tenant_id", "resource_type", "resource_id", "created_at"],
    )
    op.create_index(
        "ix_audit_tenant_trace_created_at",
        "action_audit_entries",
        ["tenant_id", "trace_id", "created_at"],
    )
    op.create_index(
        "ix_audit_tenant_correlation_created_at",
        "action_audit_entries",
        ["tenant_id", "correlation_id", "created_at"],
    )


def downgrade() -> None:
    for name in (
        "ix_audit_tenant_correlation_created_at",
        "ix_audit_tenant_trace_created_at",
        "ix_audit_tenant_resource_created_at",
        "ix_audit_tenant_outcome_severity_created_at",
        "ix_audit_tenant_category_created_at",
    ):
        op.drop_index(name, table_name="action_audit_entries")
    for name in ("correlation_id", "trace_id", "request_id", "resource_id", "resource_type", "severity", "outcome", "category"):
        op.drop_column("action_audit_entries", name)