"""Add secure passwordless challenge state."""
from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa


revision = "20260912_harden_passwordless_challenges"
down_revision = "20260912_harden_mfa_challenges"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    exists = not context.is_offline_mode() and sa.inspect(bind).has_table("passwordless_challenges")
    if context.is_offline_mode() or not exists:
        op.create_table(
            "passwordless_challenges",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("user_id", sa.String(), nullable=False),
            sa.Column("tenant_id", sa.String(128), nullable=False),
            sa.Column("token_hash", sa.String(128), nullable=False),
            sa.Column("status", sa.String(), nullable=False, server_default="pending"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        )
        op.create_index("ix_passwordless_challenges_tenant_user", "passwordless_challenges", ["tenant_id", "user_id"])
        return

    columns = {column["name"] for column in sa.inspect(bind).get_columns("passwordless_challenges")}
    if "tenant_id" not in columns:
        op.add_column("passwordless_challenges", sa.Column("tenant_id", sa.String(128), nullable=True))
    if "token_hash" not in columns:
        op.add_column("passwordless_challenges", sa.Column("token_hash", sa.String(128), nullable=True))
    if "expires_at" not in columns:
        op.add_column("passwordless_challenges", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
    if "attempts" not in columns:
        op.add_column("passwordless_challenges", sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"))
    op.execute(sa.text("UPDATE passwordless_challenges SET tenant_id = 'default' WHERE tenant_id IS NULL"))
    op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
    if "token" in columns:
        op.execute(sa.text("UPDATE passwordless_challenges SET token_hash = encode(digest(token, 'sha256'), 'hex') WHERE token_hash IS NULL AND token IS NOT NULL"))
    op.execute(sa.text("UPDATE passwordless_challenges SET token_hash = repeat('0', 64), status = 'failed' WHERE token_hash IS NULL"))
    op.execute(sa.text("UPDATE passwordless_challenges SET expires_at = created_at + interval '10 minutes' WHERE expires_at IS NULL"))
    op.alter_column("passwordless_challenges", "tenant_id", nullable=False)
    op.alter_column("passwordless_challenges", "token_hash", nullable=False)
    op.alter_column("passwordless_challenges", "expires_at", nullable=False)
    if "token" in columns:
        op.drop_column("passwordless_challenges", "token")
    op.create_index("ix_passwordless_challenges_tenant_user", "passwordless_challenges", ["tenant_id", "user_id"])


def downgrade() -> None:
    raise RuntimeError("Passwordless challenge hardening is irreversible because plaintext tokens are not recoverable")