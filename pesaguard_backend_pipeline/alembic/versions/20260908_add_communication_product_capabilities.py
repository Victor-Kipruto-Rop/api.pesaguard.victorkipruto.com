"""Add communications product capability tables."""
from alembic import op
import sqlalchemy as sa

revision = "20260908_add_communication_product_capabilities"
down_revision = "20260908_add_communication_outbox"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("communication_templates", sa.Column("id", sa.String(64), primary_key=True), sa.Column("tenant_id", sa.String(128), nullable=False), sa.Column("slug", sa.String(128), nullable=False), sa.Column("version", sa.Integer(), nullable=False, server_default="1"), sa.Column("channel", sa.String(32), nullable=False), sa.Column("body", sa.Text(), nullable=False), sa.Column("variables", sa.JSON(), nullable=False), sa.Column("status", sa.String(32), nullable=False, server_default="draft"), sa.Column("approved_by", sa.String(128)), sa.Column("approved_at", sa.DateTime(timezone=True)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.UniqueConstraint("tenant_id", "slug", "version", name="uq_communication_template_version"))
    op.create_table("communication_preferences", sa.Column("id", sa.String(64), primary_key=True), sa.Column("tenant_id", sa.String(128), nullable=False), sa.Column("recipient", sa.String(255), nullable=False), sa.Column("channels", sa.JSON(), nullable=False), sa.Column("quiet_hours_start", sa.String(5)), sa.Column("quiet_hours_end", sa.String(5)), sa.Column("timezone", sa.String(64), nullable=False, server_default="Africa/Nairobi"), sa.Column("marketing_opt_in", sa.Integer(), nullable=False, server_default="0"), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.UniqueConstraint("tenant_id", "recipient", name="uq_communication_preference_recipient"))
    op.create_table("communication_consents", sa.Column("id", sa.String(64), primary_key=True), sa.Column("tenant_id", sa.String(128), nullable=False), sa.Column("recipient", sa.String(255), nullable=False), sa.Column("channel", sa.String(32), nullable=False), sa.Column("purpose", sa.String(64), nullable=False), sa.Column("granted", sa.Integer(), nullable=False, server_default="0"), sa.Column("source", sa.String(64), nullable=False, server_default="api"), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.UniqueConstraint("tenant_id", "recipient", "channel", name="uq_communication_consent"))
    op.create_table("communication_otp_challenges", sa.Column("id", sa.String(64), primary_key=True), sa.Column("tenant_id", sa.String(128), nullable=False), sa.Column("recipient", sa.String(255), nullable=False), sa.Column("purpose", sa.String(64), nullable=False), sa.Column("code_hash", sa.String(128), nullable=False), sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"), sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False), sa.Column("consumed_at", sa.DateTime(timezone=True)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_table("communication_campaigns", sa.Column("id", sa.String(64), primary_key=True), sa.Column("tenant_id", sa.String(128), nullable=False), sa.Column("name", sa.String(255), nullable=False), sa.Column("template_id", sa.String(64), sa.ForeignKey("communication_templates.id"), nullable=False), sa.Column("channel", sa.String(32), nullable=False), sa.Column("audience", sa.JSON(), nullable=False), sa.Column("status", sa.String(32), nullable=False, server_default="draft"), sa.Column("scheduled_at", sa.DateTime(timezone=True)), sa.Column("started_at", sa.DateTime(timezone=True)), sa.Column("completed_at", sa.DateTime(timezone=True)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_table("communication_campaign_recipients", sa.Column("id", sa.String(64), primary_key=True), sa.Column("campaign_id", sa.String(64), sa.ForeignKey("communication_campaigns.id"), nullable=False), sa.Column("recipient", sa.String(255), nullable=False), sa.Column("status", sa.String(32), nullable=False, server_default="pending"), sa.Column("notification_id", sa.String(64)), sa.Column("error", sa.Text()), sa.UniqueConstraint("campaign_id", "recipient", name="uq_communication_campaign_recipient"))
    op.create_table("communication_provider_routes", sa.Column("id", sa.String(64), primary_key=True), sa.Column("tenant_id", sa.String(128), nullable=False), sa.Column("channel", sa.String(32), nullable=False), sa.Column("provider", sa.String(64), nullable=False), sa.Column("priority", sa.Integer(), nullable=False, server_default="100"), sa.Column("enabled", sa.Integer(), nullable=False, server_default="1"), sa.Column("max_daily_cost", sa.Integer()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.UniqueConstraint("tenant_id", "channel", "provider", name="uq_communication_provider_route"))


def downgrade() -> None:
    op.drop_table("communication_provider_routes")
    op.drop_table("communication_campaign_recipients")
    op.drop_table("communication_campaigns")
    op.drop_table("communication_otp_challenges")
    op.drop_table("communication_consents")
    op.drop_table("communication_preferences")
    op.drop_table("communication_templates")