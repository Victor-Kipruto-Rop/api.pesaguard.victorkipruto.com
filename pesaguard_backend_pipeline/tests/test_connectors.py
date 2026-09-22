from connectors.registry import get_connector
from event_store import ProcessResult
from ingestion import IngestionService


class FakeEventStore:
    def mark_processed(self, payload, *, tenant_id, idempotency_key_override):
        return ProcessResult.STORED


def test_connectors_share_the_same_lifecycle_and_emit_contract():
    service = IngestionService(FakeEventStore())
    connector = get_connector("safaricom-api", service, {"enabled": True})
    results = connector.ingest(
        {"data": {"transactionId": "SF-1", "amount": "12.50", "accountId": "acct-1"}},
        tenant_id="tenant-a",
    )
    assert len(results) == 1
    assert results[0].result is ProcessResult.STORED
    assert results[0].envelope.canonical.transaction_id.startswith("txn_")
    assert results[0].envelope.canonical.provider_transaction_id == "SF-1"


def test_connector_registry_removes_provider_conditionals():
    service = IngestionService(FakeEventStore())
    for source in ("mpesa", "airtel-money", "bank", "pos", "csv"):
        connector = get_connector(source, service)
        assert connector.source