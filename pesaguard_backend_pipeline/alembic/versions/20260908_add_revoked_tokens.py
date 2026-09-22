"""Add persisted JWT revocation state.

Revision ID: 20260908_add_revoked_tokens
Revises: 20260907_add_refresh_token_records
Create Date: 2026-09-08 00:00:00.000000
"""
from __future__ import annotations

from alembic import op
from alembic import context
import sqlalchemy as sa


revision = "20260908_add_revoked_tokens"
down_revision = "20260907_add_refresh_token_records"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if context.is_offline_mode() or not sa.inspect(op.get_bind()).has_table("user_accounts"):
        op.create_table(
            "user_accounts",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("tenant_id", sa.String(), nullable=False, server_default="default"),
            sa.Column("username", sa.String(), nullable=False),
            sa.Column("email", sa.String(), nullable=True),
            sa.Column("password_hash", sa.String(), nullable=True),
            sa.Column("password_salt", sa.String(), nullable=True),
            sa.Column("roles", sa.JSON(), nullable=False),
            sa.Column("permissions", sa.JSON(), nullable=False),
            sa.Column("attributes", sa.JSON(), nullable=True),
            sa.Column("mfa_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("status", sa.String(), nullable=False, server_default="active"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("id"),
        )
    op.add_column(
        "user_accounts",
        sa.Column("authorization_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_table(
        "revoked_tokens",
        sa.Column("jti", sa.String(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("jti"),
    )


def downgrade() -> None:
    op.drop_table("revoked_tokens")
    op.drop_column("user_accounts", "authorization_version")
