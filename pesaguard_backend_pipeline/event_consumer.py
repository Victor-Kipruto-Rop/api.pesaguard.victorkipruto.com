"""Consumer-group dispatch controls for versioned PesaGuard events."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from event_bus import DeliveryResult, EventDeliveryController, EventEnvelope


@dataclass(frozen=True)
class ConsumerGroup:
    name: str
    event_types: frozenset[str]


class EventConsumer:
    """Dispatch versioned events to a named consumer group."""

    def __init__(self, group: ConsumerGroup, *, controller: Optional[EventDeliveryController] = None):
        self.group = group
        self.controller = controller or EventDeliveryController()
        self.handlers: Dict[str, Callable[[EventEnvelope], Any]] = {}
        self.processed_by_type: Dict[str, int] = defaultdict(int)

    def register(self, event_type: str, handler: Callable[[EventEnvelope], Any]) -> None:
        if event_type not in self.group.event_types:
            raise ValueError(f"event type {event_type!r} is not assigned to group {self.group.name!r}")
        self.handlers[event_type] = handler

    def consume(self, event: EventEnvelope | Dict[str, Any], *, lag: int = 0, traceparent: Optional[str] = None) -> DeliveryResult:
        if isinstance(event, dict):
            event = EventEnvelope.from_dict(event)
        if event.event_type not in self.group.event_types:
            return DeliveryResult("ignored", event.event_id, event.attempt, reason="event_not_assigned_to_group")
        handler = self.handlers.get(event.event_type)
        if handler is None:
            return DeliveryResult("dead_lettered", event.event_id, event.attempt, reason="no_handler_registered")
        result = self.controller.deliver(event, handler, lag=lag, traceparent=traceparent)
        if result.status == "processed":
            self.processed_by_type[event.event_type] += 1
            from metrics import record_business_metric
            metric_name = event.event_type.replace(".", "_")
            record_business_metric(metric_name)
        return result

    def replay_dead_letters(self, *, limit: int = 100) -> list[DeliveryResult]:
        results = []
        for dead_letter in list(self.controller.dlq)[:max(0, limit)]:
            results.append(self.controller.replay(dead_letter, self.handlers[dead_letter.event.event_type]))
        return results

    def lag_snapshot(self, partition_lags: Dict[int, int]) -> Dict[str, Any]:
        from event_bus import consumer_lag_registry
        consumer_lag_registry.update(self.group.name, partition_lags)
        snapshot = self.controller.lag_snapshot(partition_lags=partition_lags)
        snapshot["consumer_group"] = self.group.name
        return snapshot


def default_consumer_groups() -> tuple[ConsumerGroup, ...]:
    return (
        ConsumerGroup("fraud", frozenset({"transaction.received", "transaction.validated", "transaction.fraud_detected"})),
        ConsumerGroup("reconciliation", frozenset({"transaction.received", "transaction.validated", "transaction.reconciled", "transaction.exception_created"})),
        ConsumerGroup("audit", frozenset({"transaction.received", "transaction.validated", "transaction.reconciled", "transaction.exception_created", "transaction.fraud_detected", "notification.requested"})),
        ConsumerGroup("alerts", frozenset({"transaction.exception_created", "transaction.fraud_detected", "notification.requested"})),
    )
