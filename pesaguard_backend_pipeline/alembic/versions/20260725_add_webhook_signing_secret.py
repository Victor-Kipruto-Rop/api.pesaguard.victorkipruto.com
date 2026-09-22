"""Add signing_secret to webhook_configs.

Required by the webhook_manager.py fix: signatures previously used
webhook_id itself as the HMAC key, but webhook_id is returned to the
customer in plaintext at registration — not a secret — so anyone who knew
a webhook's ID could forge a validly-signed payload. This adds a real,
separately-generated, non-guessable secret per webhook.

Nullable so existing rows (registered before this column existed) don't
break; webhook_manager.py logs loudly rather than silently signing
insecurely when this is NULL, until the row is backfilled or the webhook
is re-registered.

Revision ID: 20260725_add_webhook_signing_secret
Revises: 20260722_add_transaction_constraints
Create Date: 2026-07-25 00:00:00.000000
"""
from __future__ import annotations

from alembic import op
from alembic import context
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260725_add_webhook_signing_secret'
down_revision = '20260722_add_transaction_constraints'
branch_labels = None
depends_on = None


def upgrade() -> None:
    if context.is_offline_mode() or not sa.inspect(op.get_bind()).has_table('webhook_configs'):
        op.create_table(
            'webhook_configs',
            sa.Column('id', sa.String(), primary_key=True),
            sa.Column('tenant_id', sa.String(), nullable=False),
            sa.Column('url', sa.String(), nullable=False),
            sa.Column('event_types', sa.JSON(), nullable=False),
            sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
            sa.Column('retry_attempts', sa.Integer(), nullable=False, server_default='3'),
            sa.Column('timeout_seconds', sa.Integer(), nullable=False, server_default='10'),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
    op.add_column(
        'webhook_configs',
        sa.Column('signing_secret', sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('webhook_configs', 'signing_secret')
