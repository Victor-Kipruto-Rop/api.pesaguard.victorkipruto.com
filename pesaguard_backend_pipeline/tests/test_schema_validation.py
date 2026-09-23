import pytest

from event_bus import EventContractError, build_event, validate_event
from event_consumer import ConsumerGroup, EventConsumer
from schema_validation import SchemaValidationError, validate_canonical_transaction


def test_canonical_schema_rejects_missing_financial_fields():
    with pytest.raises(SchemaValidationError):
        validate_canonical_transaction({"tenant_id": "tenant-a", "TransID": "tx-1"})


def test_canonical_schema_rejects_invalid_currency():
    with pytest.raises(SchemaValidationError, match="Currency"):
        validate_canonical_transaction({
            "tenant_id": "tenant-a",
            "provider": "mpesa",
            "provider_account_id": "123456",
            "TransID": "tx-1",
            "TransAmount": "10.00",
            "Currency": "kes",
            "TransactionType": "C2B",
            "Status": "RECEIVED",
            "TransTime": "20260923120000",
            "MSISDN": "254700000001",
        })


def test_consumer_boundary_rejects_invalid_event_envelope():
    event = build_event("transaction.received", "tenant-a", "tx-1", {"TransID": "tx-1"}).to_dict()
    event.pop("payload")

    with pytest.raises(EventContractError, match="event envelope schema validation failed"):
        validate_event(event)


def test_consumer_dead_letters_invalid_event_before_handler():
    consumer = EventConsumer(ConsumerGroup("audit", frozenset({"transaction.received"})))
    result = consumer.consume({"event_id": "bad-event", "event_type": "transaction.received"})

    assert result.status == "dead_lettered"
    assert result.event_id == "bad-event"
    assert "schema_validation_failed" in result.reason