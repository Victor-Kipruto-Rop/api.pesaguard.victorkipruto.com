"""Require approval metadata for reconciliation certification cases."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260914_add_ground_truth_approval"
down_revision = "20260914_add_reconciliation_ground_truth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("reconciliation_ground_truth"):
        return
    columns = {column["name"] for column in inspector.get_columns("reconciliation_ground_truth")}
    with op.batch_alter_table("reconciliation_ground_truth") as batch:
        if "approved_by" not in columns:
            batch.add_column(sa.Column("approved_by", sa.String(128), nullable=True))
        if "approval_reference" not in columns:
            batch.add_column(sa.Column("approval_reference", sa.String(255), nullable=True))
        if "approved_at" not in columns:
            batch.add_column(sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))
    op.execute(sa.text(
        "UPDATE reconciliation_ground_truth "
        "SET approved_by = COALESCE(validated_by, 'legacy'), "
        "approval_reference = COALESCE(notes, 'legacy-ground-truth'), "
        "approved_at = COALESCE(validated_at, created_at) "
        "WHERE approved_by IS NULL"
    ))
    with op.batch_alter_table("reconciliation_ground_truth") as batch:
        batch.alter_column("approved_by", nullable=False)
        batch.alter_column("approval_reference", nullable=False)
        batch.alter_column("approved_at", nullable=False)


def downgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("reconciliation_ground_truth"):
        return
    with op.batch_alter_table("reconciliation_ground_truth") as batch:
        batch.drop_column("approved_at")
        batch.drop_column("approval_reference")
        batch.drop_column("approved_by")