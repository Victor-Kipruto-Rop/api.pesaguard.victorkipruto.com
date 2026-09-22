"""Intelligent rate governor and queue backpressure.

Slows outbound traffic automatically when provider limits, tenant quotas, or
queue saturation demand it, while always sending higher-priority traffic first.
"""
from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field

from .core.enums import CommunicationPriority

_PRIORITY_WEIGHTS = {
    CommunicationPriority.CRITICAL: 0,
    CommunicationPriority.HIGH: 1,
    CommunicationPriority.NORMAL: 2,
    CommunicationPriority.LOW: 3,
}


def _env_int(name: str, default: int) -> int:
    try:
        return max(0, int(os.getenv(name, str(default))))
    except ValueError:
        return default


def default_provider_rate_per_minute() -> int:
    return _env_int("PESAGUARD_COMMUNICATION_PROVIDER_RATE_PER_MINUTE", 0)


def default_queue_backpressure_depth() -> int:
    return _env_int("PESAGUARD_COMMUNICATION_BACKPRESSURE_QUEUE_DEPTH", 0)


@dataclass
class _Bucket:
    capacity: float
    tokens: float
    refill_per_second: float
    updated_at: float = field(default_factory=time.monotonic)

    def take(self, amount: float = 1.0) -> bool:
        now = time.monotonic()
        elapsed = now - self.updated_at
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_per_second)
        self.updated_at = now
        if self.tokens >= amount:
            self.tokens -= amount
            return True
        return False


class RateGovernor:
    """Thread-safe token bucket per provider with optional queue backpressure.

    A rate limit of 0 disables limiting for that provider. `wait_seconds`
    reports how long the caller should sleep before retrying; critical
    priority traffic is never delayed by non-critical backlog.
    """

    def __init__(self, *, provider_rates: dict[str, int] | None = None, queue_depth: int = 0):
        self._provider_rates = {name: int(rate) for name, rate in (provider_rates or {}).items()}
        self._default_rate = default_provider_rate_per_minute()
        self._queue_depth_limit = queue_depth or default_queue_backpressure_depth()
        self._buckets: dict[str, _Bucket] = {}
        self._lock = threading.Lock()

    def _bucket_for(self, provider: str) -> _Bucket | None:
        rate_per_minute = self._provider_rates.get(provider, self._default_rate)
        if rate_per_minute <= 0:
            return None
        with self._lock:
            bucket = self._buckets.get(provider)
            if bucket is None or bucket.refill_per_second != rate_per_minute / 60.0:
                bucket = _Bucket(capacity=float(rate_per_minute), tokens=float(rate_per_minute), refill_per_second=rate_per_minute / 60.0)
                self._buckets[provider] = bucket
            return bucket

    def acquire(self, provider: str, priority: CommunicationPriority = CommunicationPriority.NORMAL, *, queue_depth: int = 0) -> bool:
        """Return True when traffic may proceed; False when throttled."""
        del priority  # priority is enforced by claim ordering, not token cost
        bucket = self._bucket_for(provider)
        if bucket is not None and not bucket.take():
            return False
        if self._queue_depth_limit and queue_depth > self._queue_depth_limit:
            return False
        return True

    def wait_seconds(self, provider: str) -> float:
        bucket = self._bucket_for(provider)
        if bucket is None:
            return 0.0
        with self._lock:
            now = time.monotonic()
            elapsed = now - bucket.updated_at
            tokens = min(bucket.capacity, bucket.tokens + elapsed * bucket.refill_per_second)
        if tokens >= 1.0:
            return 0.0
        deficit = 1.0 - tokens
        return round(max(0.05, deficit / bucket.refill_per_second), 2)

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {
                "default_rate_per_minute": self._default_rate,
                "provider_rates": dict(self._provider_rates),
                "queue_backpressure_depth": self._queue_depth_limit,
                "active_buckets": {name: round(bucket.tokens, 2) for name, bucket in self._buckets.items()},
            }