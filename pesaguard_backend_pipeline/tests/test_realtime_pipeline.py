from event_bus import build_event
from realtime_pipeline import RealtimeTransactionPipeline


def _received():
    return build_event(
        "transaction.received",
        "tenant-a",
        "tx-1",
        {
            "TransID": "tx-1",
            "TransAmount": "10",
            "Currency": "kes",
            "provider": "mpesa",
            "provider_account_id": "123456",
        },
        source="mpesa",
        source_event_id="provider-event-1",
    )


def test_realtime_pipeline_preserves_lineage_across_stages():
    published = []
    pipeline = RealtimeTransactionPipeline(publisher=published.append)
    validated = pipeline.validate(_received())
    normalized = pipeline.normalize(validated)
    enriched = pipeline.enrich(normalized)
    processed = pipeline.process(enriched)

    assert [event.event_type for event in published] == [
        "transaction.validated",
        "transaction.normalized",
        "transaction.enriched",
        "transaction.processed",
    ]
    assert normalized.payload["TransAmount"] == "10.00"
    assert normalized.payload["Currency"] == "KES"
    assert enriched.payload["enrichment"]["enriched_by"] == "pesaguard.realtime_pipeline"
    assert normalized.causation_id == validated.event_id
    assert processed.causation_id == enriched.event_id
    assert processed.correlation_id == validated.correlation_id
    assert processed.source == "mpesa"
