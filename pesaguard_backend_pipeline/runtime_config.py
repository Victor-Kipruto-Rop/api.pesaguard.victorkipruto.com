from __future__ import annotations

import os
from dataclasses import dataclass


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


@dataclass(frozen=True)
class RuntimeConfig:
    public_api_url: str
    api_body_limit: int
    webhook_body_limit: int
    api_rate_limit_per_minute: int
    tenant_id: str
    kafka_topic: str
    redis_url: str
    admin_api_token: str
    daraja_consumer_key: str
    daraja_consumer_secret: str
    port: int

    @classmethod
    def from_env(cls) -> "RuntimeConfig":
        return cls(
            public_api_url=os.getenv("PESAGUARD_API_URL", "https://api.pesaguard.victorkipruto.com").rstrip("/"),
            api_body_limit=_int_env("PESAGUARD_API_MAX_BODY_BYTES", 1048576),
            webhook_body_limit=_int_env("PESAGUARD_WEBHOOK_MAX_BODY_BYTES", 1048576),
            api_rate_limit_per_minute=_int_env("PESAGUARD_API_RATE_LIMIT_PER_MINUTE", 60),
            tenant_id=os.getenv("TENANT_ID", "default"),
            kafka_topic=os.getenv("KAFKA_TOPIC_TRANSACTIONS", "mpesa.transactions.raw"),
            redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            admin_api_token=os.getenv("PESAGUARD_ADMIN_API_TOKEN", ""),
            daraja_consumer_key=os.getenv("DARAJA_CONSUMER_KEY", ""),
            daraja_consumer_secret=os.getenv("DARAJA_CONSUMER_SECRET", ""),
            port=_int_env("PORT", 5001),
        )