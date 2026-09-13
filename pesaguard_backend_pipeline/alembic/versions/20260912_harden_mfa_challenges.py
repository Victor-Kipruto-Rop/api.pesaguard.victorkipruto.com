"""Harden MFA challenge storage and lifecycle state."""
from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa


revision = "20260912_harden_mfa_challenges"
down_revision = "20260909_harden_tenant_api_keys"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if context.is_offline_mode() or not sa.inspect(bind).has_table("mfa_challenges"):
        op.create_table(
            "mfa_challenges",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("user_id", sa.String(), nullable=False),
            sa.Column("tenant_id", sa.String(128), nullable=False),
            sa.Column("code_hash", sa.String(128), nullable=False),
            sa.Column("status", sa.String(), nullable=False, server_default="pending"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        )
        op.create_index("ix_mfa_challenges_tenant_user", "mfa_challenges", ["tenant_id", "user_id"])
        return

    columns = {column["name"] for column in sa.inspect(bind).get_columns("mfa_challenges")}
    if "tenant_id" not in columns:
        op.add_column("mfa_challenges", sa.Column("tenant_id", sa.String(128), nullable=True))
    if "code_hash" not in columns:
        op.add_column("mfa_challenges", sa.Column("code_hash", sa.String(128), nullable=True))
    if "expires_at" not in columns:
        op.add_column("mfa_challenges", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
    if "attempts" not in columns:
        op.add_column("mfa_challenges", sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"))
    op.execute(sa.text("UPDATE mfa_challenges SET tenant_id = 'default' WHERE tenant_id IS NULL"))
    op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
    if "code" in columns:
        op.execute(sa.text("UPDATE mfa_challenges SET code_hash = encode(digest(code, 'sha256'), 'hex') WHERE code_hash IS NULL"))
    else:
        op.execute(sa.text("UPDATE mfa_challenges SET code_hash = repeat('0', 64), status = 'failed' WHERE code_hash IS NULL"))
    op.execute(sa.text("UPDATE mfa_challenges SET expires_at = created_at + interval '10 minutes' WHERE expires_at IS NULL"))
    op.alter_column("mfa_challenges", "tenant_id", nullable=False)
    op.alter_column("mfa_challenges", "code_hash", nullable=False)
    op.alter_column("mfa_challenges", "expires_at", nullable=False)
    if "code" in columns:
        op.drop_column("mfa_challenges", "code")
    op.create_index("ix_mfa_challenges_tenant_user", "mfa_challenges", ["tenant_id", "user_id"])


def downgrade() -> None:
    op.add_column("mfa_challenges", sa.Column("code", sa.String(), nullable=True))
    op.execute(sa.text("UPDATE mfa_challenges SET code = code_hash"))
    op.alter_column("mfa_challenges", "code", nullable=False)
    op.drop_index("ix_mfa_challenges_tenant_user", table_name="mfa_challenges")
    op.drop_column("mfa_challenges", "attempts")
    op.drop_column("mfa_challenges", "expires_at")
    op.drop_column("mfa_challenges", "code_hash")
    op.drop_column("mfa_challenges", "tenant_id")