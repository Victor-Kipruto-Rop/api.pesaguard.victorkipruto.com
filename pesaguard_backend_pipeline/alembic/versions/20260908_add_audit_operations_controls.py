"""Add audit retention, legal hold, and privacy control tables."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260908_add_audit_operations_controls"
down_revision = "20260908_add_audit_outbox"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_retention_policies",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("audit_retention_days", sa.Integer(), nullable=False, server_default="365"),
        sa.Column("archive_before_expiry", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("privacy_mode", sa.String(length=32), nullable=False, server_default="strict"),
        sa.Column("updated_by", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", name="uq_audit_retention_policy_tenant"),
    )
    op.create_table(
        "audit_legal_holds",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("scope_type", sa.String(length=32), nullable=False),
        sa.Column("scope_id", sa.String(length=255), nullable=True),
        sa.Column("reason", sa.String(length=4096), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("placed_by", sa.String(length=255), nullable=False),
        sa.Column("placed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("released_by", sa.String(length=255), nullable=True),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_legal_hold_tenant_active", "audit_legal_holds", ["tenant_id", "active"])
    op.create_index("ix_audit_legal_hold_scope", "audit_legal_holds", ["tenant_id", "scope_type", "scope_id", "active"])
    op.create_table(
        "audit_privacy_settings",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("pseudonymize_actors", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("pseudonymize_resources", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("include_details", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("updated_by", sa.String(length=255), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", name="uq_audit_privacy_settings_tenant"),
    )


def downgrade() -> None:
    op.drop_table("audit_privacy_settings")
    op.drop_index("ix_audit_legal_hold_scope", table_name="audit_legal_holds")
    op.drop_index("ix_audit_legal_hold_tenant_active", table_name="audit_legal_holds")
    op.drop_table("audit_legal_holds")
    op.drop_table("audit_retention_policies")