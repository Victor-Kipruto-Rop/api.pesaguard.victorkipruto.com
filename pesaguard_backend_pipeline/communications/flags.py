"""Feature flags for gradual rollout of communication capabilities.

Flags default to safe values and are controlled via environment variables so
operations can disable a capability without a deployment.
"""
from __future__ import annotations

import os

_FLAG_DEFAULTS: dict[str, bool] = {
    "AFRICASTALKING_SMS": True,
    "AFRICASTALKING_USSD": False,
    "AFRICASTALKING_VOICE": False,
    "AFRICASTALKING_WHATSAPP": False,
    "PROVIDER_FAILOVER": True,
    "SMART_ROUTING": True,
    "AI_COMMUNICATIONS": False,
    "CAMPAIGNS": True,
    "BULK_SMS": True,
}


def is_enabled(flag: str) -> bool:
    if flag not in _FLAG_DEFAULTS:
        raise ValueError(f"unknown communication feature flag: {flag}")
    raw = os.getenv(f"PESAGUARD_FLAG_{flag}")
    if raw is None:
        return _FLAG_DEFAULTS[flag]
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def snapshot() -> dict[str, bool]:
    return {flag: is_enabled(flag) for flag in _FLAG_DEFAULTS}