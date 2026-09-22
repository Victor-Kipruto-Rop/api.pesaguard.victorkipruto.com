"""Daraja HMAC signature validator helpers.

This module supports both the legacy callback signature style used in the app and
more explicit header-based validation required by the webhook integration tests.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
from typing import Dict, Optional

_HEX_CHARS = set("0123456789abcdefABCDEF")


def compute_hmac(secret_or_body, body_or_secret, algo: str = "sha256") -> bytes:
    """Compute an HMAC digest for a raw payload.

    Supports both helper call styles used across the codebase:
    compute_hmac(secret, body) and compute_hmac(body, secret).
    """
    if isinstance(secret_or_body, (bytes, bytearray)) and isinstance(body_or_secret, (str, bytes, bytearray)):
        body = bytes(secret_or_body)
        secret = str(body_or_secret)
    else:
        secret = str(secret_or_body)
        body = bytes(body_or_secret)

    if not isinstance(body, (bytes, bytearray)):
        raise TypeError("body must be bytes")
    digestmod = getattr(hashlib, algo)
    return hmac.new(secret.encode("utf-8"), bytes(body), digestmod).digest()


def _strip_prefix(signature: str) -> str:
    value = (signature or "").strip()
    if "=" in value:
        prefix, remainder = value.split("=", 1)
        if prefix.lower().startswith("sha"):
            value = remainder
    return value.strip()


def _decode_hex(candidate: str) -> Optional[bytes]:
    if not candidate or len(candidate) % 2 != 0:
        return None
    if any(ch not in _HEX_CHARS for ch in candidate):
        return None
    try:
        return bytes.fromhex(candidate)
    except ValueError:
        return None


def _decode_base64(candidate: str) -> Optional[bytes]:
    try:
        padding = "=" * ((4 - len(candidate) % 4) % 4)
        return base64.b64decode(candidate + padding, validate=True)
    except Exception:
        return None


def _looks_like_signature(value: object) -> bool:
    if value is None:
        return False
    candidate = _strip_prefix(str(value)).strip()
    if not candidate:
        return False
    if _decode_hex(candidate) is not None:
        return True
    if _decode_base64(candidate) is not None:
        return True
    return False


def validate_signature(arg1, arg2, arg3=None, *, algo: str = "sha256", signature_encoding: str = "hex") -> bool:
    """Validate a hexadecimal or base64 signature against the computed HMAC.

    Supports both the canonical secret/body/signature ordering and the legacy
    signature/body/secret ordering used by older code paths.
    """
    if arg3 is None:
        raise TypeError("validate_signature requires secret/body/signature arguments")

    if not isinstance(arg2, (bytes, bytearray)):
        raise TypeError("validate_signature requires a body payload in bytes form")

    body = bytes(arg2)

    def _scan(secret_value, signature_value):
        if signature_value is None:
            return False
        normalized = _strip_prefix(str(signature_value))
        decoded_candidates = []
        if signature_encoding == "hex":
            decoded_candidates.extend([_decode_hex(normalized), _decode_base64(normalized)])
        elif signature_encoding == "base64":
            decoded_candidates.extend([_decode_base64(normalized), _decode_hex(normalized)])
        else:
            decoded_candidates.extend([_decode_hex(normalized), _decode_base64(normalized)])

        expected = compute_hmac(str(secret_value), body, algo=algo)
        for candidate in decoded_candidates:
            if candidate is not None and hmac.compare_digest(candidate, expected):
                return True
        return False

    # Canonical order: validate_signature(secret, body, signature)
    if isinstance(arg1, str) and isinstance(arg3, str):
        if _scan(arg1, arg3):
            return True
        if _scan(arg3, arg1):
            return True

    if isinstance(arg1, (bytes, bytearray)) and isinstance(arg3, str):
        legacy_signature = str(arg1.decode("utf-8", errors="ignore"))
        if _scan(arg3, legacy_signature):
            return True

    # Legacy compatibility: validate_signature(signature, body, secret)
    if isinstance(arg1, str) and isinstance(arg3, str):
        if _looks_like_signature(arg1) and not _looks_like_signature(arg3):
            if _scan(arg3, arg1):
                return True

    return False


def validate_daraja_callback(
    body_or_headers,
    signature_or_body,
    consumer_secret: Optional[str] = None,
    *,
    header_name: str = "X-MPESA-SIGNATURE",
    signature_encoding: str = "hex",
) -> bool:
    """Validate a Daraja callback using either a raw body/signature pair or headers."""
    if isinstance(body_or_headers, (bytes, bytearray)):
        body = bytes(body_or_headers)
        signature = str(signature_or_body or "")
        secret = str(consumer_secret or "")
        return validate_signature(secret, body, signature)

    headers = body_or_headers or {}
    body = bytes(signature_or_body or b"")
    secret = str(consumer_secret or "")
    header_value = headers.get(header_name) or headers.get(header_name.lower()) or ""
    if not header_value and headers:
        for key, value in headers.items():
            if str(key).lower() in {"x-daraja-signature", "x-mpesa-signature"}:
                header_value = str(value)
                break
    if signature_encoding == "hex":
        return validate_signature(secret, body, header_value)
    if signature_encoding == "base64":
        expected = compute_hmac(secret, body)
        try:
            normalized = base64.b64encode(expected).decode("ascii")
        except Exception:
            return False
        return hmac.compare_digest(str(header_value).strip(), normalized)
    raise ValueError("signature_encoding must be 'hex' or 'base64'")
