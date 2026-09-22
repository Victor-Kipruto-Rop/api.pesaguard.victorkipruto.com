"""Merge migration chain heads after webhook index branch.

Reconciles the two heads introduced when 20260914_add_fraud_risk_assessments
and 20260917_add_webhook_delivery_tenant_webhook_index both descended from
20260914_repair_dead_letter_created_at. This revision performs no schema or
data changes; it only restores a single linear migration history so that
`alembic upgrade head` works for deployments.

Revision ID: 20260923_merge_fraud_and_lineage_heads
"""
from __future__ import annotations

from alembic import op  # noqa: F401  (kept for consistency with other revisions)


revision = "20260923_merge_fraud_and_lineage_heads"
down_revision = (
    "20260914_add_fraud_risk_assessments",
    "20260923_add_lineage_records",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Merge revision: no schema or data changes.
    pass


def downgrade() -> None:
    # Downgrading a merge restores the two-head state; no schema or data changes.
    pass
