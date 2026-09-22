"""Application-level protection for persisted provider payloads and identifiers."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from typing import Any

from cryptography.fernet import Fernet

_ENCRYPTED_PREFIX = "enc:v1:"
_SENSITIVE_KEYS = {
    "msisdn",
    "phone",
    "phone_number",
    "account_number",
    "bank_account",
    "customer_name",
    "national_id",
    "id_number",
    "authorization_code",
    "conversation_id",
}


def _configured_secret() -> str:
    secret = os.getenv("PESAGUARD_PAYLOAD_ENCRYPTION_KEY") or os.getenv("PROVIDER_ENCRYPTION_KEY")
    if not secret:
        if os.getenv("PESAGUARD_ENVIRONMENT", "development").lower() in {"production", "prod"}:
            raise RuntimeError("PESAGUARD_PAYLOAD_ENCRYPTION_KEY must be configured in production")
        secret = os.getenv("JWT_SECRET_KEY", "development-payload-key")
    return secret


def _fernet() -> Fernet:
    key = base64.urlsafe_b64encode(hashlib.sha256(_configured_secret().encode("utf-8")).digest())
    return Fernet(key)


def encrypt_value(value: Any) -> str:
    plaintext = json.dumps(value, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    return _ENCRYPTED_PREFIX + _fernet().encrypt(plaintext).decode("ascii")


def decrypt_value(value: Any) -> Any:
    if not isinstance(value, str) or not value.startswith(_ENCRYPTED_PREFIX):
        return value
    plaintext = _fernet().decrypt(value[len(_ENCRYPTED_PREFIX):].encode("ascii"))
    return json.loads(plaintext)


def tokenize_identifier(value: Any) -> str:
    """Return a deterministic keyed token suitable for equality lookup and logs."""
    pepper = _configured_secret().encode("utf-8")
    normalized = str(value or "").strip().encode("utf-8")
    return "tok:v1:" + hmac.new(pepper, normalized, hashlib.sha256).hexdigest()


def protect_payload(payload: Any) -> Any:
    """Encrypt sensitive leaf values while preserving payload shape and non-sensitive fields."""
    if isinstance(payload, dict):
        protected = {}
        for key, value in payload.items():
            if key.lower() in _SENSITIVE_KEYS and value not in (None, ""):
                protected[key] = encrypt_value(value)
            else:
                protected[key] = protect_payload(value)
        return protected
    if isinstance(payload, list):
        return [protect_payload(item) for item in payload]
    return payload


def unprotect_payload(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {key: unprotect_payload(value) for key, value in payload.items()}
    if isinstance(payload, list):
        return [unprotect_payload(item) for item in payload]
    return decrypt_value(payload)
