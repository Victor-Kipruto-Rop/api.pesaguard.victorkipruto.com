from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum

from ..core.enums import CommunicationChannel
from ..core.error_categories import ProviderErrorCategory, category_for_exception, failover_eligible
from ..core.exceptions import CommunicationError
from ..core.interfaces import CommunicationProvider, NotificationRequest, ProviderMessage


class CircuitState(StrEnum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    """Per-provider circuit breaker with CLOSED/OPEN/HALF_OPEN transitions."""

    def __init__(self, name: str, *, failure_threshold: int = 5, recovery_seconds: int = 60, half_open_max_calls: int = 3):
        self.name = name
        self.failure_threshold = max(1, failure_threshold)
        self.recovery_seconds = max(0, recovery_seconds)
        self.half_open_max_calls = max(1, half_open_max_calls)
        self.state = CircuitState.CLOSED
        self.consecutive_failures = 0
        self.half_open_calls = 0
        self.opened_at: float | None = None
        self.last_error_category: str | None = None
        self._lock = threading.Lock()

    def allow(self) -> bool:
        with self._lock:
            if self.state == CircuitState.OPEN:
                if self.opened_at is not None and time.monotonic() - self.opened_at > self.recovery_seconds:
                    self.state = CircuitState.HALF_OPEN
                    self.half_open_calls = 0
                    return False
                else:
                    return False
            if self.state == CircuitState.HALF_OPEN:
                if self.half_open_calls >= self.half_open_max_calls:
                    return False
                self.half_open_calls += 1
            return True

    def record_success(self) -> None:
        with self._lock:
            self.consecutive_failures = 0
            self.half_open_calls = 0
            self.state = CircuitState.CLOSED
            self.opened_at = None

    def record_failure(self, category: ProviderErrorCategory | None = None) -> None:
        with self._lock:
            self.consecutive_failures += 1
            if category is not None:
                self.last_error_category = category.value
            if self.state == CircuitState.HALF_OPEN or self.consecutive_failures >= self.failure_threshold:
                self.state = CircuitState.OPEN
                self.opened_at = time.monotonic()

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {
                "provider": self.name,
                "state": self.state.value,
                "consecutive_failures": self.consecutive_failures,
                "failure_threshold": self.failure_threshold,
                "recovery_seconds": self.recovery_seconds,
                "last_error_category": self.last_error_category,
            }


@dataclass
class ProviderHealth:
    failures: int = 0
    unavailable_until: datetime | None = None
    successes: int = 0
    total_latency_ms: float = 0.0
    last_error_category: str | None = None
    breakers: dict[str, CircuitBreaker] = field(default_factory=dict)

    def breaker(self, name: str, **kwargs: object) -> CircuitBreaker:
        breaker = self.breakers.get(name)
        if breaker is None:
            breaker = CircuitBreaker(name, **kwargs)  # type: ignore[arg-type]
            self.breakers[name] = breaker
        return breaker

    @property
    def average_latency_ms(self) -> float:
        total = self.successes + self.failures
        return round(self.total_latency_ms / total, 1) if total else 0.0


class ProviderRouter:
    """Route sends through ordered providers with circuit-breaker-aware failover.

    Failover happens only for infrastructure degradation (timeout, network,
    availability, rate limiting). Permanent errors (invalid recipient, invalid
    request, authentication misconfiguration) are raised immediately so bad
    traffic is never retried against a healthy backup provider.
    """

    def __init__(
        self,
        providers: dict[str, CommunicationProvider],
        order: dict[CommunicationChannel, list[str]],
        *,
        failure_threshold: int = 3,
        cooldown_seconds: int = 60,
        half_open_max_calls: int = 2,
    ):
        self.providers = providers
        self.order = order
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.health = {name: ProviderHealth() for name in providers}

    def send(self, request: NotificationRequest) -> ProviderMessage:
        errors: list[CommunicationError] = []
        for name in self.order.get(request.channel, []):
            provider = self.providers.get(name)
            state = self.health.setdefault(name, ProviderHealth())
            if provider is None:
                continue
            breaker = state.breaker(name, failure_threshold=self.failure_threshold, recovery_seconds=self.cooldown_seconds)
            if not breaker.allow():
                continue
            started = time.perf_counter()
            try:
                result = provider.send(request)
                state.successes += 1
                state.total_latency_ms += int((time.perf_counter() - started) * 1000)
                breaker.record_success()
                return result
            except CommunicationError as exc:
                state.total_latency_ms += int((time.perf_counter() - started) * 1000)
                category = category_for_exception(exc)
                state.last_error_category = category.value
                breaker.record_failure(category)
                if failover_eligible(category):
                    errors.append(exc)
                    state.failures += 1
                    continue
                raise
            except Exception as exc:  # unexpected failure: treat as provider unavailability
                state.failures += 1
                breaker.record_failure(ProviderErrorCategory.PROVIDER_UNAVAILABLE)
                errors.append(CommunicationError(str(exc), code="PROVIDER_UNAVAILABLE", retryable=True))
        if errors:
            raise errors[-1]
        raise CommunicationError(
            f"no healthy provider configured for {request.channel.value}",
            code="PROVIDER_UNAVAILABLE",
            retryable=True,
        )

    def snapshot(self) -> dict[str, object]:
        """Expose per-provider circuit state and counters for monitoring."""
        return {
            name: {
                **state.breaker(name, failure_threshold=self.failure_threshold, recovery_seconds=self.cooldown_seconds).snapshot(),
                "successes": state.successes,
                "failures": state.failures,
                "average_latency_ms": state.average_latency_ms,
                "last_error_category": state.last_error_category,
            }
            for name, state in self.health.items()
        }