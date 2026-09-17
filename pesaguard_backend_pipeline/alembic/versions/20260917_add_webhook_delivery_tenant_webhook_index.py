"""Add the tenant/webhook composite index used by scoped delivery history."""

from alembic import op
import sqlalchemy as sa


revision = "20260917_add_webhook_delivery_tenant_webhook_index"
down_revision = "20260914_repair_dead_letter_created_at"
branch_labels = None
depends_on = None


INDEX_NAME = "ix_webhook_deliveries_tenant_webhook"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("webhook_deliveries"):
        return
    indexes = {index["name"] for index in inspector.get_indexes("webhook_deliveries")}
    if INDEX_NAME not in indexes:
        op.create_index(INDEX_NAME, "webhook_deliveries", ["tenant_id", "webhook_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("webhook_deliveries"):
        return
    indexes = {index["name"] for index in inspector.get_indexes("webhook_deliveries")}
    if INDEX_NAME in indexes:
        op.drop_index(INDEX_NAME, table_name="webhook_deliveries")
