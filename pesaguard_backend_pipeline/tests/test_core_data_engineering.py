from datetime import datetime, timedelta, timezone
from decimal import Decimal

from core_data_engineering import CoreDataEngineering, InMemoryDataRepository


def payload(reference="tx-1", amount="12.50"):
    return {
        "TransID": reference,
        "TransAmount": amount,
        "TransTime": "20260923120000",
        "MSISDN": "254700000001",
        "Currency": "KES",
    }


def test_api_event_and_batch_share_idempotent_canonical_pipeline():
    pipeline = CoreDataEngineering()

    accepted = pipeline.ingest_api("tenant-a", payload())
    duplicate = pipeline.ingest_event("tenant-a", payload())
    summary = pipeline.ingest_batch("tenant-a", [payload("tx-2", "2.10"), {"TransID": "bad"}])

    assert accepted is not None
    assert duplicate is None
    assert accepted.amount == Decimal("12.50")
    assert summary == {"accepted": 1, "duplicates": 0, "rejected": 1}
    assert pipeline.lineage_for("tenant-a", accepted.event_id).has_stage("normalized")


def test_aggregation_is_tenant_scoped_and_partitioned():
    pipeline = CoreDataEngineering()
    record = pipeline.ingest_api("tenant-a", payload())
    pipeline.ingest_api("tenant-b", payload("other", "99.99"))

    assert pipeline.aggregate("tenant-a") == {"KES": {"count": 1, "amount": "12.50"}}
    assert pipeline.partition_key(record) == "tenant=tenant-a/year=2026/month=09"


def test_retention_archives_before_delete():
    repository = InMemoryDataRepository()
    pipeline = CoreDataEngineering(repository)
    record = pipeline.ingest_api("tenant-a", payload())
    old_time = record.occurred_at + timedelta(days=366)

    assert pipeline.apply_retention("tenant-a", now=old_time) == 1
    assert repository.archived == [record]
    assert list(repository.records("tenant-a")) == []


class Connector:
    name = "ledger"

    def read(self, *, tenant_id, cursor=None, limit=500):
        assert tenant_id == "tenant-a"
        return [payload("connector-1", "3.25")]


def test_connector_ingestion_uses_same_controls():
    pipeline = CoreDataEngineering()
    assert pipeline.ingest_connector(Connector(), "tenant-a") == {
        "accepted": 1,
        "duplicates": 0,
        "rejected": 0,
    }