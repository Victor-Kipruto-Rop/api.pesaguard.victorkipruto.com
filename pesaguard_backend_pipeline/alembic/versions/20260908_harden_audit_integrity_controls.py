"""Harden audit integrity, sequencing, leases, and compliance metadata."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260908_harden_audit_integrity_controls"
down_revision = "20260908_add_audit_operations_controls"
branch_labels = None
depends_on = None


def _add_column(table: str, name: str, column_type, **kwargs) -> None:
    op.add_column(table, sa.Column(name, column_type, **kwargs))


def upgrade() -> None:
    audit_columns = (
        ("schema_version", sa.Integer(), {"nullable": False, "server_default": "1"}),
        ("hash_version", sa.Integer(), {"nullable": False, "server_default": "1"}),
        ("tenant_sequence", sa.Integer(), {"nullable": True}),
        ("actor_id", sa.String(length=255), {"nullable": True}),
        ("actor_type", sa.String(length=32), {"nullable": False, "server_default": "system"}),
        ("actor_display_name", sa.String(length=255), {"nullable": True}),
        ("actor_authentication_method", sa.String(length=64), {"nullable": True}),
    )
    for name, column_type, kwargs in audit_columns:
        _add_column("action_audit_entries", name, column_type, **kwargs)
    # SQLite is used for migration smoke tests; these constraints and triggers
    # are PostgreSQL-specific and remain enforced by the production database.
    if op.get_bind().dialect.name == "sqlite":
        return
    op.create_unique_constraint("uq_audit_id_tenant", "action_audit_entries", ["id", "tenant_id"])
    op.create_unique_constraint("uq_audit_tenant_sequence", "action_audit_entries", ["tenant_id", "tenant_sequence"])
    op.create_check_constraint("ck_audit_category", "action_audit_entries", "category IN ('access', 'authentication', 'compliance', 'configuration', 'data', 'operations', 'security', 'system')")
    op.create_check_constraint("ck_audit_outcome", "action_audit_entries", "outcome IN ('success', 'failure', 'denied', 'partial')")
    op.create_check_constraint("ck_audit_severity", "action_audit_entries", "severity IN ('debug', 'info', 'notice', 'warning', 'critical')")
    op.create_check_constraint("ck_audit_actor_type", "action_audit_entries", "actor_type IN ('user', 'service', 'system', 'anonymous', 'worker', 'admin')")
    op.create_check_constraint("ck_audit_versions_positive", "action_audit_entries", "schema_version > 0 AND hash_version > 0")
    op.create_check_constraint("ck_audit_tenant_sequence_positive", "action_audit_entries", "tenant_sequence IS NULL OR tenant_sequence > 0")
    op.create_check_constraint("ck_audit_signature_requirements", "action_audit_entries", "signature IS NULL OR (event_hash IS NOT NULL AND signature_algorithm = 'Ed25519' AND signature_key_id IS NOT NULL)")
    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION prevent_action_audit_mutation()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
                RAISE EXCEPTION 'audit entries are append-only';
            END;
            $$
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE TRIGGER action_audit_entries_append_only_update
            BEFORE UPDATE ON action_audit_entries
            FOR EACH ROW EXECUTE FUNCTION prevent_action_audit_mutation()
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE TRIGGER action_audit_entries_append_only_delete
            BEFORE DELETE ON action_audit_entries
            FOR EACH ROW EXECUTE FUNCTION prevent_action_audit_mutation()
            """
        )
    )

    outbox_columns = (
        ("lease_owner", sa.String(length=255), {"nullable": True}),
        ("lease_expires_at", sa.DateTime(timezone=True), {"nullable": True}),
        ("last_attempt_at", sa.DateTime(timezone=True), {"nullable": True}),
        ("backoff_strategy", sa.String(length=32), {"nullable": False, "server_default": "exponential_jitter"}),
        ("retry_after", sa.Integer(), {"nullable": True}),
        ("last_http_status", sa.Integer(), {"nullable": True}),
        ("last_provider_code", sa.String(length=64), {"nullable": True}),
        ("replay_count", sa.Integer(), {"nullable": False, "server_default": "0"}),
        ("replayed_by", sa.String(length=255), {"nullable": True}),
        ("replayed_at", sa.DateTime(timezone=True), {"nullable": True}),
        ("replay_reason", sa.String(length=4096), {"nullable": True}),
    )
    for name, column_type, kwargs in outbox_columns:
        _add_column("audit_outbox_entries", name, column_type, **kwargs)
    op.create_check_constraint("ck_audit_outbox_status", "audit_outbox_entries", "status IN ('pending', 'in_progress', 'delivered', 'failed', 'dead_letter')")
    op.create_check_constraint("ck_audit_outbox_attempt_counts", "audit_outbox_entries", "attempt_count >= 0 AND max_attempts > 0")
    op.create_foreign_key(
        "fk_audit_outbox_audit_tenant",
        "audit_outbox_entries",
        "action_audit_entries",
        ["audit_id", "tenant_id"],
        ["id", "tenant_id"],
    )
    op.create_index("ix_audit_outbox_lease_expiry", "audit_outbox_entries", ["status", "lease_expires_at"])

    op.create_table(
        "audit_signing_keys",
        sa.Column("key_id", sa.String(length=128), nullable=False),
        sa.Column("algorithm", sa.String(length=32), nullable=False, server_default="Ed25519"),
        sa.Column("public_key", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("key_id"),
        sa.CheckConstraint("algorithm = 'Ed25519'", name="ck_audit_key_algorithm"),
        sa.CheckConstraint("status IN ('active', 'verification_only', 'retired', 'revoked')", name="ck_audit_key_status"),
    )

    hold_columns = (
        ("hold_type", sa.String(length=32), {"nullable": False, "server_default": "regulatory"}),
        ("release_reason", sa.String(length=4096), {"nullable": True}),
        ("expires_at", sa.DateTime(timezone=True), {"nullable": True}),
        ("created_at", sa.DateTime(timezone=True), {"nullable": False, "server_default": sa.func.now()}),
        ("updated_at", sa.DateTime(timezone=True), {"nullable": False, "server_default": sa.func.now()}),
    )
    for name, column_type, kwargs in hold_columns:
        _add_column("audit_legal_holds", name, column_type, **kwargs)
    _add_column("audit_privacy_settings", "privacy_mode", sa.String(length=32), nullable=False, server_default="strict")
    op.create_check_constraint("ck_audit_privacy_mode", "audit_privacy_settings", "privacy_mode IN ('strict', 'standard', 'internal', 'regulated')")
    op.create_check_constraint("ck_audit_retention_days_positive", "audit_retention_policies", "audit_retention_days > 0")


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS action_audit_entries_append_only_update ON action_audit_entries")
    op.execute("DROP TRIGGER IF EXISTS action_audit_entries_append_only_delete ON action_audit_entries")
    op.execute("DROP FUNCTION IF EXISTS prevent_action_audit_mutation()")
    op.drop_constraint("ck_audit_privacy_mode", "audit_privacy_settings", type_="check")
    op.drop_constraint("ck_audit_retention_days_positive", "audit_retention_policies", type_="check")
    op.drop_column("audit_privacy_settings", "privacy_mode")
    for name in ("updated_at", "created_at", "expires_at", "release_reason", "hold_type"):
        op.drop_column("audit_legal_holds", name)
    op.drop_table("audit_signing_keys")
    op.drop_index("ix_audit_outbox_lease_expiry", table_name="audit_outbox_entries")
    op.drop_constraint("fk_audit_outbox_audit_tenant", "audit_outbox_entries", type_="foreignkey")
    op.drop_constraint("ck_audit_outbox_attempt_counts", "audit_outbox_entries", type_="check")
    op.drop_constraint("ck_audit_outbox_status", "audit_outbox_entries", type_="check")
    for name in ("replay_reason", "replayed_at", "replayed_by", "replay_count", "last_provider_code", "last_http_status", "retry_after", "backoff_strategy", "last_attempt_at", "lease_expires_at", "lease_owner"):
        op.drop_column("audit_outbox_entries", name)
    op.drop_constraint("ck_audit_signature_requirements", "action_audit_entries", type_="check")
    op.drop_constraint("ck_audit_versions_positive", "action_audit_entries", type_="check")
    op.drop_constraint("ck_audit_actor_type", "action_audit_entries", type_="check")
    op.drop_constraint("ck_audit_severity", "action_audit_entries", type_="check")
    op.drop_constraint("ck_audit_outcome", "action_audit_entries", type_="check")
    op.drop_constraint("ck_audit_category", "action_audit_entries", type_="check")
    op.drop_constraint("ck_audit_tenant_sequence_positive", "action_audit_entries", type_="check")
    op.drop_constraint("uq_audit_tenant_sequence", "action_audit_entries", type_="unique")
    op.drop_constraint("uq_audit_id_tenant", "action_audit_entries", type_="unique")
    for name in ("actor_authentication_method", "actor_display_name", "actor_type", "actor_id", "tenant_sequence", "hash_version", "schema_version"):
        op.drop_column("action_audit_entries", name)