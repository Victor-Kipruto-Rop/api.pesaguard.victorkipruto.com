"""Add persisted refresh-token rotation state.

Revision ID: 20260907_add_refresh_token_records
Revises: 20260726_add_payment_providers
Create Date: 2026-09-07 00:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260907_add_refresh_token_records"
down_revision = "20260726_add_payment_providers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "refresh_token_records",
        sa.Column("jti", sa.String(), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column("family_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("username", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=True),
        sa.Column("device_id", sa.String(), nullable=True),
        sa.Column("user_agent", sa.String(), nullable=True),
        sa.Column("ip_address", sa.String(), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("family_revoked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.PrimaryKeyConstraint("jti"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_refresh_token_records_token_hash", "refresh_token_records", ["token_hash"])
    op.create_index("ix_refresh_token_records_family_id", "refresh_token_records", ["family_id"])


def downgrade() -> None:
    op.drop_index("ix_refresh_token_records_family_id", table_name="refresh_token_records")
    op.drop_index("ix_refresh_token_records_token_hash", table_name="refresh_token_records")
    op.drop_table("refresh_token_records")
