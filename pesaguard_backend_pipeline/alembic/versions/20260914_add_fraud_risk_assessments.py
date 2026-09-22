"""Persist explainable fraud risk decisions."""

from alembic import op
import sqlalchemy as sa

revision = "20260914_add_fraud_risk_assessments"
down_revision = "20260914_repair_dead_letter_created_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if "fraud_risk_assessments" in sa.inspect(bind).get_table_names():
        return
    op.create_table(
        "fraud_risk_assessments",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("transaction_id", sa.String(), nullable=False),
        sa.Column("risk_score", sa.Numeric(6, 4), nullable=False),
        sa.Column("risk_level", sa.String(16), nullable=False),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("reason_codes", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("model_version", sa.String(64), nullable=False),
        sa.Column("rules_triggered", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("features", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "transaction_id", name="uq_fraud_risk_tenant_transaction"),
        sa.CheckConstraint("risk_score >= 0 AND risk_score <= 1", name="ck_fraud_risk_score_range"),
        sa.CheckConstraint("risk_level IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')", name="ck_fraud_risk_level"),
    )
    op.create_index("ix_fraud_risk_tenant_level", "fraud_risk_assessments", ["tenant_id", "risk_level", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_fraud_risk_tenant_level", table_name="fraud_risk_assessments")
    op.drop_table("fraud_risk_assessments")
