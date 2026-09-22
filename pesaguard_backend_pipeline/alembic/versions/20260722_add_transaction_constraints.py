"""Add unique constraint and indices for webhook idempotency and performance.

Revision ID: 20260722_add_transaction_constraints
Revises: 20260719_add_deadletters_reports_audit
Create Date: 2026-07-22 07:00:00.000000

"""
from __future__ import annotations

from alembic import op
from alembic import context
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260722_add_transaction_constraints'
down_revision = '20260719_add_deadletters_reports_audit'
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = None if context.is_offline_mode() else sa.inspect(op.get_bind())
    if context.is_offline_mode() or not inspector.has_table('transactions'):
        op.create_table(
            'transactions',
            sa.Column('trans_id', sa.String(), primary_key=True),
            sa.Column('trans_amount', sa.Float(), nullable=False),
            sa.Column('msisdn', sa.String(), nullable=False),
            sa.Column('business_short_code', sa.String(), nullable=False),
            sa.Column('trans_time', sa.String(), nullable=False),
            sa.Column('raw_payload', sa.JSON(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
    if context.is_offline_mode() or not inspector.has_table('discrepancies'):
        op.create_table(
            'discrepancies',
            sa.Column('id', sa.String(), primary_key=True),
            sa.Column('trans_id', sa.String(), nullable=False),
            sa.Column('tenant_id', sa.String(), nullable=True),
            sa.Column('anomaly_type', sa.String(), nullable=False),
            sa.Column('status', sa.String(), nullable=False, server_default='needs_review'),
            sa.Column('severity', sa.String(), nullable=False, server_default='warning'),
            sa.Column('details', sa.Text(), nullable=True),
            sa.Column('resolved', sa.Boolean(), nullable=False, server_default=sa.text('false')),
            sa.Column('detected_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('resolution_note', sa.Text(), nullable=True),
            sa.Column('latency_seconds', sa.Integer(), nullable=True),
            sa.Column('assignee', sa.String(), nullable=True),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('timeline', sa.JSON(), nullable=True),
        )
    # Add unique constraint to transactions.trans_id (idempotency key)
    with op.batch_alter_table('transactions') as batch_op:
        batch_op.create_unique_constraint(
            'uq_transaction_trans_id',
            ['trans_id']
        )
    
    # Add indices for query performance
    op.create_index(
        'ix_transaction_trans_id',
        'transactions',
        ['trans_id'],
        unique=False
    )
    op.create_index(
        'ix_transaction_created_at',
        'transactions',
        ['created_at'],
        unique=False
    )
    
    # Add indices to discrepancies table for filtering and joins
    op.create_index(
        'ix_discrepancy_trans_id',
        'discrepancies',
        ['trans_id'],
        unique=False
    )
    op.create_index(
        'ix_discrepancy_tenant_id',
        'discrepancies',
        ['tenant_id'],
        unique=False
    )
    op.create_index(
        'ix_discrepancy_detected_at',
        'discrepancies',
        ['detected_at'],
        unique=False
    )


def downgrade() -> None:
    # Remove indices and constraint
    op.drop_index('ix_discrepancy_detected_at', table_name='discrepancies')
    op.drop_index('ix_discrepancy_tenant_id', table_name='discrepancies')
    op.drop_index('ix_discrepancy_trans_id', table_name='discrepancies')
    op.drop_index('ix_transaction_created_at', table_name='transactions')
    op.drop_index('ix_transaction_trans_id', table_name='transactions')
    with op.batch_alter_table('transactions') as batch_op:
        batch_op.drop_constraint('uq_transaction_trans_id', type_='unique')
