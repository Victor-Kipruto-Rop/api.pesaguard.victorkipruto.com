"""Add tenant scope to outbound webhook delivery audit records."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260913_add_webhook_delivery_tenant_scope"
down_revision = "20260913_add_tenant_scope_constraints"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("webhook_deliveries"):
        return
    columns = {column["name"] for column in inspector.get_columns("webhook_deliveries")}
    if "tenant_id" not in columns:
        with op.batch_alter_table("webhook_deliveries") as batch_op:
            batch_op.add_column(sa.Column("tenant_id", sa.String(), nullable=True, server_default="default"))
        op.execute(sa.text("UPDATE webhook_deliveries SET tenant_id = 'default' WHERE tenant_id IS NULL"))
        with op.batch_alter_table("webhook_deliveries") as batch_op:
            batch_op.alter_column("tenant_id", existing_type=sa.String(), nullable=False, server_default="default")

    constraints = {
        constraint["name"]
        for constraint in inspector.get_check_constraints("webhook_deliveries")
    }
    if "ck_webhook_deliveries_tenant_id_nonempty" not in constraints:
        with op.batch_alter_table("webhook_deliveries") as batch_op:
            batch_op.create_check_constraint(
                "ck_webhook_deliveries_tenant_id_nonempty",
                "tenant_id IS NOT NULL AND tenant_id <> ''",
            )

    indexes = {index["name"] for index in inspector.get_indexes("webhook_deliveries")}
    if "ix_webhook_deliveries_tenant_created" not in indexes:
        op.create_index(
            "ix_webhook_deliveries_tenant_created",
            "webhook_deliveries",
            ["tenant_id", "created_at"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("webhook_deliveries"):
        return
    indexes = {index["name"] for index in inspector.get_indexes("webhook_deliveries")}
    if "ix_webhook_deliveries_tenant_created" in indexes:
        op.drop_index("ix_webhook_deliveries_tenant_created", table_name="webhook_deliveries")
    columns = {column["name"] for column in inspector.get_columns("webhook_deliveries")}
    if "tenant_id" in columns:
        with op.batch_alter_table("webhook_deliveries") as batch_op:
            batch_op.drop_constraint("ck_webhook_deliveries_tenant_id_nonempty", type="check")
            batch_op.drop_column("tenant_id")
