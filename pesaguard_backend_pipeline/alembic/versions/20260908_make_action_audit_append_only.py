"""Enforce append-only action audit entries and database privileges."""
from __future__ import annotations

import os
import re

from alembic import op
import sqlalchemy as sa


revision = "20260908_make_action_audit_append_only"
down_revision = "20260908_encrypt_provider_configuration"
branch_labels = None
depends_on = None

_ROLE_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")


def _configured_role(name: str) -> str | None:
    role = os.getenv(name)
    if role and not _ROLE_PATTERN.fullmatch(role):
        raise RuntimeError(f"{name} contains an invalid PostgreSQL role name")
    return role


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return

    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION reject_action_audit_mutation()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
                RAISE EXCEPTION 'action_audit_entries are append-only';
            END;
            $$
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE TRIGGER action_audit_entries_append_only
            BEFORE UPDATE OR DELETE ON action_audit_entries
            FOR EACH ROW EXECUTE FUNCTION reject_action_audit_mutation()
            """
        )
    )
    op.execute(sa.text("REVOKE UPDATE, DELETE, TRUNCATE ON action_audit_entries FROM PUBLIC"))

    reader_role = _configured_role("PESAGUARD_AUDIT_READER_ROLE")
    writer_role = _configured_role("PESAGUARD_AUDIT_WRITER_ROLE")
    if reader_role:
        op.execute(sa.text(f'GRANT SELECT ON action_audit_entries TO "{reader_role}"'))
    if writer_role:
        op.execute(sa.text(f'GRANT INSERT ON action_audit_entries TO "{writer_role}"'))


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return

    op.execute(sa.text("DROP TRIGGER IF EXISTS action_audit_entries_append_only ON action_audit_entries"))
    op.execute(sa.text("DROP FUNCTION IF EXISTS reject_action_audit_mutation()"))