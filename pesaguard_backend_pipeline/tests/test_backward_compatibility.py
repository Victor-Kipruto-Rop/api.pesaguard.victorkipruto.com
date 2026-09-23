import json
from pathlib import Path

from api_validation import validate_transaction_create
from event_bus import validate_event
from event_consumer import ConsumerGroup, EventConsumer


def test_v2_event_consumer_accepts_v1_event_fixture():
    event = json.loads((Path(__file__).parent / "fixtures" / "event_v1.json").read_text(encoding="utf-8"))
    consumer = EventConsumer(ConsumerGroup("audit", frozenset({"transaction.received"})))
    seen = []
    consumer.register("transaction.received", lambda received: seen.append(received.event_id))

    result = consumer.consume(event)

    assert result.status == "processed"
    assert seen == ["evt-v1-legacy"]


def test_v2_api_validator_accepts_legacy_v1_transaction_fields():
    validate_transaction_create({
        "TransID": "legacy-tx-1",
        "BusinessShortCode": "123456",
        "provider": "mpesa",
        "TransAmount": "10.00",
        "Currency": "KES",
        "MSISDN": "254700000000",
        "TransTime": "20260923120000",
    })