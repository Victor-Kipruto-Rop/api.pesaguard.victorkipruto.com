import time

import pytest

from event_bus import EventContractError, EventDeliveryController, RetryPolicy, build_event, event_fingerprint, validate_event
from event_consumer import ConsumerGroup, EventConsumer
from producer import publish_versioned_event


def _event(event_type="transaction.received", event_id="evt-1"):
    return build_event(
        event_type,
        "tenant-a",
        "tx-1",
        {"TransID": "tx-1", "amount": "10.00"},
        event_id=event_id,
        correlation_id="corr-1",
    )


def test_versioned_event_contract_and_topic_routing():
    event = _event()
    assert event_fingerprint(event)
    sent_args, sent_kwargs = publish_versioned_event(event, producer=type("Producer", (), {"send": lambda self, *args, **kwargs: (args, kwargs)})())
    assert sent_args[0] == "pesaguard.transactions.raw"
    assert sent_kwargs["value"]["schema_version"] == "1.0"
    assert sent_kwargs["value"]["source"] == "pesaguard"
    with pytest.raises(EventContractError):
        build_event("unsupported.event", "tenant-a", "tx-1", {})

def test_event_catalog_accepts_required_transaction_and_operational_events():
    for event_type in (
        "transaction.rejected",
        "transaction.completed",
        "reconciliation.started",
        "reconciliation.exception.detected",
        "fraud.analysis.started",
        "fraud.anomaly.reviewed",
        "notification.exhausted",
        "batch.record.rejected",
        "audit.event.created",
    ):
        assert build_event(event_type, "tenant-a", "tx-1", {}).event_type == event_type


def test_first_class_event_contract_accepts_timestamp_and_preserves_lineage():
    event = validate_event({
        "event_id": "evt-123",
        "event_type": "transaction.created",
        "event_version": 1,
        "schema_version": "1.0",
        "source": "mpesa",
        "tenant_id": "tenant-001",
        "aggregate_id": "txn-001",
        "timestamp": "2026-09-23T00:00:00Z",
        "correlation_id": "corr-001",
        "payload": {"amount": "2500.00"},
        "metadata": {"source_ip": "internal"},
    })
    assert event.timestamp == "2026-09-23T00:00:00Z"
    assert event.occurred_at == event.timestamp
    assert event.source == "mpesa"
    assert event.metadata["source_ip"] == "internal"


def test_duplicate_event_is_processed_once():
    seen = []
    consumer = EventConsumer(ConsumerGroup("audit", frozenset({"transaction.received"})))
    consumer.register("transaction.received", lambda event: seen.append(event.event_id))
    event = _event()
    assert consumer.consume(event).status == "processed"
    assert consumer.consume(event).status == "duplicate"
    assert seen == [event.event_id]


def test_consumer_crash_retries_then_dead_letters_poison_message():
    controller = EventDeliveryController(retry_policy=RetryPolicy(max_attempts=3, base_delay_seconds=0.01))
    consumer = EventConsumer(ConsumerGroup("fraud", frozenset({"transaction.received"})), controller=controller)
    consumer.register("transaction.received", lambda event: (_ for _ in ()).throw(RuntimeError("poison")))
    event = _event(event_id="poison")
    assert consumer.consume(event).status == "retry_scheduled"
    retry = controller.due_retries(now=time.time() + 1)[0].event
    assert consumer.consume(retry).status == "retry_scheduled"
    retry = controller.due_retries(now=time.time() + 2)[0].event
    assert consumer.consume(retry).status == "dead_lettered"
    assert len(controller.dlq) == 1


def test_dlq_replay_and_slow_consumer_backpressure():
    controller = EventDeliveryController(retry_policy=RetryPolicy(max_attempts=1), max_lag=5)
    consumer = EventConsumer(ConsumerGroup("audit", frozenset({"transaction.received"})), controller=controller)
    processed = []
    consumer.register("transaction.received", lambda event: processed.append(event.event_id))
    event = _event(event_id="replay")
    consumer.controller.deliver(event, lambda _: (_ for _ in ()).throw(RuntimeError("temporary")))
    assert len(controller.dlq) == 1
    consumer.handlers["transaction.received"] = lambda item: processed.append(item.event_id)
    assert consumer.replay_dead_letters()[0].status == "processed"
    assert processed == ["replay"]
    assert consumer.consume(_event(event_id="lagged"), lag=6).status == "backpressured"
    snapshot = consumer.lag_snapshot({0: 6})
    assert snapshot["backpressured"] is True


def test_replay_preserves_event_identity_after_retry_exhaustion(tmp_path):
    """A transient failure that exhausts retries must be dead-lettered and replayed
    without changing event identity, and metrics must reflect retries, DLQ placement,
    and successful replay processing.

    This is the first replay-focused failure simulation for the Phase 10
    chaos/resilience extension: poison/failed-event path that triggers DLQ,
    retry, alert, and replay.
    """
    from event_bus import RetryPolicy

    from metrics import record_business_metric, telemetry_snapshot

    controller = EventDeliveryController(
        retry_policy=RetryPolicy(max_attempts=3, base_delay_seconds=0.001),
    )
    consumer = EventConsumer(
        ConsumerGroup("reconciliation", frozenset({"transaction.received"})),
        controller=controller,
    )

    event_id = "replay-identity"
    original_event = build_event(
        "transaction.received",
        "tenant-a",
        "tx-replay",
        {"TransID": "tx-replay", "amount": "12.00"},
        event_id=event_id,
        correlation_id="corr-replay",
    )

    processed_ids = []
    dlq_placer_called = {"n": 0}

    class TransactionalHandler:
        def __call__(self, event):
            raise RuntimeError("transient failure")

    def record_transaction_received(event):
        processed_ids.append(event.event_id)
        record_business_metric("transaction_received")


    consumer.register("transaction.received", TransactionalHandler())

    result = consumer.consume(original_event)
    assert result.status == "retry_scheduled"
    assert result.attempt == 1

    # Drain scheduled retries until the event dies.
    attempt = 1
    while result.status == "retry_scheduled":
        attempt += 1
        retry_event = controller.due_retries(now=time.time() + 10)[0].event
        result = consumer.consume(retry_event)

    assert result.status == "dead_lettered", result.reason
    assert len(controller.dlq) == 1
    assert controller.dlq[0].event.event_id == event_id
    assert controller.dlq[0].event.correlation_id == "corr-replay"
    assert controller.dlq[0].event.tenant_id == "tenant-a"
    assert controller.dlq[0].event.aggregate_id == "tx-replay"
    assert controller.dlq[0].event.payload["TransID"] == "tx-replay"

    snapshot = telemetry_snapshot()
    assert snapshot["event_retries"] >= 2
    assert snapshot["business"]["dlq_events"] >= 1

    after_dlq_snapshot = snapshot

    consumer.handlers["transaction.received"] = record_transaction_received

    replay_results = consumer.replay_dead_letters(limit=10)
    assert len(replay_results) == 1
    assert replay_results[0].status == "processed"
    assert replay_results[0].attempt == 1
    assert replay_results[0].event_id == event_id
    assert processed_ids == [event_id]

    assert len(controller.dlq) == 0

    final_snapshot = telemetry_snapshot()
    assert final_snapshot["event_retries"] == snapshot["event_retries"]
    assert final_snapshot["business"]["dlq_events"] == after_dlq_snapshot["business"][
        "dlq_events"
    ]
    assert final_snapshot["business"].get("transaction_received", 0) == after_dlq_snapshot[
        "business"
    ].get("transaction_received", 0) + 1

def test_broker_unavailable_raises_without_acknowledging_event(monkeypatch):
    import producer

    monkeypatch.setattr(producer._producer_manager, "get_producer", lambda: (_ for _ in ()).throw(ConnectionError("broker unavailable")))
    monkeypatch.setattr(producer, "_fallback_to_dead_letter_queue", lambda *args: None)
    producer._circuit_breaker.state = "CLOSED"
    producer._circuit_breaker.failure_count = 0
    with pytest.raises(ConnectionError):
        producer.publish_transaction_event("mpesa.transactions.raw", {"TransID": "broker-down"})


def test_batch_publish_preserves_per_message_delivery_results(monkeypatch):
    import producer

    class Future:
        def __init__(self, error=None):
            self.error = error

        def get(self, timeout):
            if self.error:
                raise self.error
            return object()

    class BatchProducer:
        def __init__(self):
            self.sent = []

        def send(self, topic, **kwargs):
            self.sent.append((topic, kwargs["value"]))
            return Future(TimeoutError("one item timed out") if len(self.sent) == 2 else None)

        def flush(self, timeout):
            return None

    batch_producer = BatchProducer()
    monkeypatch.setattr(producer._producer_manager, "get_producer", lambda: batch_producer)
    monkeypatch.setattr(producer._circuit_breaker, "can_execute", lambda: True)
    monkeypatch.setattr(producer._circuit_breaker, "record_success", lambda: None)
    monkeypatch.setattr(producer._circuit_breaker, "record_failure", lambda: None)

    results = producer.publish_transaction_batch_results(
        "mpesa.transactions.raw",
        [{"TransID": "tx-1"}, {"TransID": "tx-2"}, {"TransID": "tx-3"}],
    )

    assert results == [True, False, True]
    assert [payload["TransID"] for _, payload in batch_producer.sent] == ["tx-1", "tx-2", "tx-3"]


def test_network_failure_is_retried_then_dead_lettered():
    controller = EventDeliveryController(retry_policy=RetryPolicy(max_attempts=3, base_delay_seconds=0.001))
    consumer = EventConsumer(ConsumerGroup("reconciliation", frozenset({"transaction.received"})), controller=controller)
    consumer.register("transaction.received", lambda event: (_ for _ in ()).throw(TimeoutError("network timeout")))
    event = _event(event_id="network-failure")
    result = consumer.consume(event)
    assert result.status == "retry_scheduled"
    for attempt in range(2):
        retry = controller.due_retries(now=time.time() + 10)[0].event
        result = consumer.consume(retry)
    assert result.status == "dead_lettered"
