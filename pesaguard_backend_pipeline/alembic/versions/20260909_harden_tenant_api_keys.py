"""Add tenant-scoped identity and hashed API-key lifecycle metadata."""
from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa

revision = "20260909_harden_tenant_api_keys"
down_revision = "20260909_scope_transaction_identity"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    return context.is_offline_mode() or sa.inspect(op.get_bind()).has_table(name)


def _columns(name: str) -> set[str]:
    if context.is_offline_mode():
        return set()
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(name)}


def upgrade() -> None:
    if _has_table("internal_records"):
        if "tenant_id" not in _columns("internal_records"):
            op.add_column("internal_records", sa.Column("tenant_id", sa.String(), nullable=True))
            op.execute(sa.text("UPDATE internal_records SET tenant_id = 'default' WHERE tenant_id IS NULL"))
            op.alter_column("internal_records", "tenant_id", nullable=False, server_default="default")
        op.create_index(
            "ix_internal_records_tenant_phone",
            "internal_records",
            ["tenant_id", "phone_number"],
            if_not_exists=True,
        )

    if _has_table("discrepancies"):
        if "tenant_id" in _columns("discrepancies"):
            op.execute(sa.text("UPDATE discrepancies SET tenant_id = 'default' WHERE tenant_id IS NULL"))
            op.alter_column("discrepancies", "tenant_id", nullable=False, server_default="default")
        op.create_index("ix_discrepancy_tenant_id", "discrepancies", ["tenant_id"], if_not_exists=True)

    if not _has_table("api_key_records"):
        op.create_table(
            "api_key_records",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("tenant_id", sa.String(), nullable=False, server_default="default"),
            sa.Column("key_hash", sa.String(128), nullable=False),
            sa.Column("key_prefix", sa.String(32), nullable=False),
            sa.Column("role", sa.String(), nullable=False, server_default="read-only"),
            sa.Column("scopes", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("rotated_from_id", sa.String(), nullable=True),
            sa.Column("api_metadata", sa.JSON(), nullable=True),
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("key_hash", name="uq_api_key_records_key_hash"),
        )
        op.create_index("ix_api_key_records_key_hash", "api_key_records", ["key_hash"], unique=True)
        op.create_index("ix_api_key_records_tenant_active", "api_key_records", ["tenant_id", "active"])


def downgrade() -> None:
    raise RuntimeError("API-key hardening migration is irreversible because plaintext keys are not recoverable")
