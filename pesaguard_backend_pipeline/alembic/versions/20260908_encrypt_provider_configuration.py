"""Encrypt existing payment provider configuration secrets."""
from __future__ import annotations

import base64
import hashlib
import json
import os

from alembic import context, op
import sqlalchemy as sa
from cryptography.fernet import Fernet


revision = "20260908_encrypt_provider_configuration"
down_revision = "20260908_add_revoked_tokens"
branch_labels = None
depends_on = None

_SECRET_KEYS = {
    "secret", "client_secret", "api_key", "access_token", "private_key", "password",
    "consumer_key", "consumer_secret", "token", "signing_secret",
}


def _cipher() -> Fernet:
    configured_key = os.getenv("PROVIDER_ENCRYPTION_KEY") or os.getenv("JWT_SECRET_KEY")
    if not configured_key:
        raise RuntimeError("PROVIDER_ENCRYPTION_KEY must be configured to migrate provider secrets")
    key = base64.urlsafe_b64encode(hashlib.sha256(configured_key.encode("utf-8")).digest())
    return Fernet(key)


def _encrypt(cipher: Fernet, value):
    if isinstance(value, dict):
        return {
            key: _encrypt(cipher, item) if key.lower() in _SECRET_KEYS else _protect_nested(cipher, item)
            for key, item in value.items()
        }
    return value


def _protect_nested(cipher: Fernet, value):
    if isinstance(value, dict):
        return {key: _encrypt(cipher, item) if key.lower() in _SECRET_KEYS else _protect_nested(cipher, item) for key, item in value.items()}
    if isinstance(value, list):
        return [_protect_nested(cipher, item) for item in value]
    return value


def _encrypt_credentials(cipher: Fernet, value):
    if not isinstance(value, dict):
        return value
    return {key: _encrypt_scalar(cipher, item) for key, item in value.items()}


def _encrypt_scalar(cipher: Fernet, value):
    if isinstance(value, dict):
        return {key: _encrypt_scalar(cipher, item) for key, item in value.items()}
    if isinstance(value, list):
        return [_encrypt_scalar(cipher, item) for item in value]
    if isinstance(value, str) and value.startswith("enc:v1:"):
        return value
    plaintext = json.dumps(value, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return "enc:v1:" + cipher.encrypt(plaintext).decode("ascii")


def upgrade() -> None:
    if context.is_offline_mode():
        return
    bind = op.get_bind()
    provider_table = sa.table(
        "payment_providers",
        sa.column("id", sa.String()),
        sa.column("credentials", sa.JSON()),
        sa.column("api_configuration", sa.JSON()),
        sa.column("account_configuration", sa.JSON()),
        sa.column("webhook_configuration", sa.JSON()),
    )
    rows = bind.execute(sa.select(provider_table)).mappings().all()
    if not rows:
        return
    cipher = _cipher()
    for row in rows:
        bind.execute(
            provider_table.update().where(provider_table.c.id == row["id"]).values(
                credentials=_encrypt_credentials(cipher, row["credentials"] or {}),
                api_configuration=_protect_nested(cipher, row["api_configuration"] or {}),
                account_configuration=_protect_nested(cipher, row["account_configuration"] or {}),
                webhook_configuration=_protect_nested(cipher, row["webhook_configuration"] or {}),
            )
        )


def downgrade() -> None:
    raise RuntimeError("Encrypted provider configuration cannot be safely downgraded")
