"""Add tenant-scoped payment provider management."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260726_add_payment_providers"
down_revision = "20260725_add_webhook_signing_secret"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "payment_providers",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("provider_type", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("credentials", sa.JSON(), nullable=False),
        sa.Column("api_configuration", sa.JSON(), nullable=False),
        sa.Column("account_configuration", sa.JSON(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("supported_currencies", sa.JSON(), nullable=False),
        sa.Column("capabilities", sa.JSON(), nullable=False),
        sa.Column("webhook_configuration", sa.JSON(), nullable=False),
        sa.Column("connection_status", sa.String(), nullable=False),
        sa.Column("connection_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("health_status", sa.String(), nullable=False),
        sa.Column("health_details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_payment_providers_tenant_id", "payment_providers", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_payment_providers_tenant_id", table_name="payment_providers")
    op.drop_table("payment_providers")