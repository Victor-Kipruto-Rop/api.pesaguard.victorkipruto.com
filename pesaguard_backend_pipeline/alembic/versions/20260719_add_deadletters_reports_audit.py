"""create dead_letters, reports, action_audit_entries

Revision ID: 20260719_add_deadletters_reports_audit
Revises: 
Create Date: 2026-07-19 00:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260719_add_deadletters_reports_audit'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'dead_letters',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('tenant_id', sa.String(), nullable=True, index=True),
        sa.Column('reason', sa.String(), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=True),
        sa.Column('error_detail', sa.Text(), nullable=True),
        sa.Column('attempts', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('processed', sa.Boolean(), nullable=True, server_default=sa.text('false')),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('received_at', sa.DateTime(timezone=True), nullable=True, index=True),
    )

    op.create_table(
        'reports',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('tenant_id', sa.String(), nullable=False, index=True),
        sa.Column('report_type', sa.String(), nullable=False),
        sa.Column('period_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('period_end', sa.DateTime(timezone=True), nullable=False),
        sa.Column('content', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='generated'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True, index=True),
        sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        'action_audit_entries',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('tenant_id', sa.String(), nullable=False, index=True),
        sa.Column('actor', sa.String(), nullable=False),
        sa.Column('action', sa.String(), nullable=False, index=True),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True, index=True),
    )


def downgrade() -> None:
    op.drop_table('action_audit_entries')
    op.drop_table('reports')
    op.drop_table('dead_letters')
