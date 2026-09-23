from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine

from event_bus import EventContractError, build_event, validate_event
from event_consumer import ConsumerGroup, EventConsumer
from event_store import EventStore, ProcessResult
from models import Base, Transaction
from producer import publish_versioned_event


def _transaction_payload():
    return {
        "TransID": "contract-tx-1",
        "TransAmount": "10.00",
        "MSISDN": "254700000000",
        "BusinessShortCode": "123456",
        "TransTime": "20260923120000",
        "provider": "mpesa",
        "tenant_id": "tenant-a",
    }


class CapturingProducer:
    def __init__(self):
        self.messages = []

    def send(self, topic, **kwargs):
        self.messages.append((topic, kwargs))
        return SimpleNamespace(get=lambda timeout: SimpleNamespace(topic=topic, partition=0, offset=0))


def test_producer_generates_valid_versioned_event_envelope():
    event = build_event("transaction.received", "tenant-a", "contract-tx-1", _transaction_payload(), event_id="contract-event-1")
    producer = CapturingProducer()

    publish_versioned_event(event, producer=producer)
    topic, message = producer.messages[0]
    received = validate_event(message["value"])

    assert topic == "pesaguard.transactions.raw"
    assert received.event_id == "contract-event-1"
    assert received.event_version == 1
    assert received.schema_version == "1.0"
    assert received.tenant_id == "tenant-a"
    assert received.payload["TransID"] == "contract-tx-1"


def test_consumer_accepts_optional_and_unknown_metadata_fields():
    event = build_event(
        "transaction.received",
        "tenant-a",
        "contract-tx-2",
        _transaction_payload(),
        metadata={"new_optional_field": "accepted"},
    ).to_dict()
    event["future_field"] = "ignored"
    consumer = EventConsumer(ConsumerGroup("audit", frozenset({"transaction.received"})))
    seen = []
    consumer.register("transaction.received", lambda received: seen.append(received.metadata["new_optional_field"]))

    assert consumer.consume(event).status == "processed"
    assert seen == ["accepted"]


def test_consumer_rejects_invalid_event_contract():
    consumer = EventConsumer(ConsumerGroup("audit", frozenset({"transaction.received"})))
    result = consumer.consume({"event_id": "invalid", "event_type": "transaction.received"})

    assert result.status == "dead_lettered"
    assert "schema_validation_failed" in result.reason


def test_consumer_to_postgres_contract_is_idempotent(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'contract.db'}"
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    store = EventStore(database_url=database_url)
    consumer = EventConsumer(ConsumerGroup("transaction", frozenset({"transaction.received"})))
    consumer.register(
        "transaction.received",
        lambda event: store.mark_processed(event.payload, tenant_id=event.tenant_id),
    )
    event = build_event("transaction.received", "tenant-a", "contract-tx-3", _transaction_payload(), event_id="contract-event-3")

    assert consumer.consume(event).status == "processed"
    assert store.mark_processed(event.payload, tenant_id=event.tenant_id) is ProcessResult.DUPLICATE
    from sqlalchemy.orm import sessionmaker
    with sessionmaker(bind=engine)() as session:
        assert session.query(Transaction).count() == 1