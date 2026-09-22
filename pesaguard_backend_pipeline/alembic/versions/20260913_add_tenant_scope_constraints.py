"""Add database-level tenant non-empty constraints for financial and event tables."""

from alembic import op
import sqlalchemy as sa


revision = "20260913_add_tenant_scope_constraints"
down_revision = "20260913_add_immutable_financial_history"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    for table_name, constraint_name, expr in (
        ("transactions", "ck_transactions_tenant_id_nonempty", "tenant_id IS NOT NULL AND tenant_id <> ''"),
        ("processed_transactions", "ck_processed_tenant_id_nonempty", "tenant_id IS NOT NULL AND tenant_id <> ''"),
        ("transaction_events", "ck_transaction_events_tenant_id_nonempty", "tenant_id IS NOT NULL AND tenant_id <> ''"),
        ("transaction_outbox", "ck_transaction_outbox_tenant_id_nonempty", "tenant_id IS NOT NULL AND tenant_id <> ''"),
        ("reconciliation_outbox", "ck_reconciliation_outbox_tenant_id_nonempty", "tenant_id IS NOT NULL AND tenant_id <> ''"),
        ("discrepancies", "ck_discrepancy_tenant_id_nonempty", "tenant_id IS NOT NULL AND tenant_id <> ''"),
        ("discrepancy_events", "ck_discrepancy_events_tenant_id_nonempty", "tenant_id IS NOT NULL AND tenant_id <> ''"),
        ("internal_records", "ck_internal_records_tenant_id_nonempty", "tenant_id IS NOT NULL AND tenant_id <> ''"),
        ("webhook_configs", "ck_webhook_configs_tenant_id_nonempty", "tenant_id IS NOT NULL AND tenant_id <> ''"),
        ("escalation_rules", "ck_escalation_rules_tenant_id_nonempty", "tenant_id IS NOT NULL AND tenant_id <> ''"),
        ("on_call_rotations", "ck_on_call_rotations_tenant_id_nonempty", "tenant_id IS NOT NULL AND tenant_id <> ''"),
        ("email_notifications", "ck_email_notifications_tenant_id_nonempty", "tenant_id IS NOT NULL AND tenant_id <> ''"),
        ("dead_letters", "ck_dead_letters_tenant_id_nonempty", "tenant_id IS NOT NULL AND tenant_id <> ''"),
        ("reports", "ck_reports_tenant_id_nonempty", "tenant_id IS NOT NULL AND tenant_id <> ''"),
        ("user_accounts", "ck_user_accounts_tenant_id_nonempty", "tenant_id IS NOT NULL AND tenant_id <> ''"),
        ("organizations", "ck_organizations_tenant_id_nonempty", "tenant_id IS NOT NULL AND tenant_id <> ''"),
        ("teams", "ck_teams_tenant_id_nonempty", "tenant_id IS NOT NULL AND tenant_id <> ''"),
        ("departments", "ck_departments_tenant_id_nonempty", "tenant_id IS NOT NULL AND tenant_id <> ''"),
        ("organization_memberships", "ck_organization_memberships_tenant_id_nonempty", "tenant_id IS NOT NULL AND tenant_id <> ''"),
        ("organization_approvals", "ck_organization_approvals_tenant_id_nonempty", "tenant_id IS NOT NULL AND tenant_id <> ''"),
    ):
        if table_name not in tables:
            continue
        constraints = {constraint["name"] for constraint in inspector.get_check_constraints(table_name)}
        if constraint_name not in constraints:
            op.create_check_constraint(constraint_name, table_name, expr)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    for table_name, constraint_name in (
        ("transactions", "ck_transactions_tenant_id_nonempty"),
        ("processed_transactions", "ck_processed_tenant_id_nonempty"),
        ("transaction_events", "ck_transaction_events_tenant_id_nonempty"),
        ("transaction_outbox", "ck_transaction_outbox_tenant_id_nonempty"),
        ("reconciliation_outbox", "ck_reconciliation_outbox_tenant_id_nonempty"),
        ("discrepancies", "ck_discrepancy_tenant_id_nonempty"),
        ("discrepancy_events", "ck_discrepancy_events_tenant_id_nonempty"),
        ("internal_records", "ck_internal_records_tenant_id_nonempty"),
        ("webhook_configs", "ck_webhook_configs_tenant_id_nonempty"),
        ("webhook_deliveries", "ck_webhook_deliveries_tenant_id_nonempty"),
        ("escalation_rules", "ck_escalation_rules_tenant_id_nonempty"),
        ("on_call_rotations", "ck_on_call_rotations_tenant_id_nonempty"),
        ("email_notifications", "ck_email_notifications_tenant_id_nonempty"),
        ("dead_letters", "ck_dead_letters_tenant_id_nonempty"),
        ("reports", "ck_reports_tenant_id_nonempty"),
        ("user_accounts", "ck_user_accounts_tenant_id_nonempty"),
        ("organizations", "ck_organizations_tenant_id_nonempty"),
        ("teams", "ck_teams_tenant_id_nonempty"),
        ("departments", "ck_departments_tenant_id_nonempty"),
        ("organization_memberships", "ck_organization_memberships_tenant_id_nonempty"),
        ("organization_approvals", "ck_organization_approvals_tenant_id_nonempty"),
        ("tenant_configurations", "ck_tenant_configurations_tenant_id_nonempty"),
        ("tenant_limits", "ck_tenant_limits_tenant_id_nonempty"),
        ("tenant_usage", "ck_tenant_usage_tenant_id_nonempty"),
        ("user_sessions", "ck_user_sessions_tenant_id_nonempty"),
        ("oidc_providers", "ck_oidc_providers_tenant_id_nonempty"),
        ("payment_providers", "ck_payment_providers_tenant_id_nonempty"),
        ("api_key_records", "ck_api_key_records_tenant_id_nonempty"),
        ("mfa_challenges", "ck_mfa_challenges_tenant_id_nonempty"),
        ("passwordless_challenges", "ck_passwordless_challenges_tenant_id_nonempty"),
    ):
        if table_name not in tables:
            continue
        constraints = {constraint["name"] for constraint in inspector.get_check_constraints(table_name)}
        if constraint_name in constraints:
            op.drop_constraint(constraint_name, table_name, type_="check")
