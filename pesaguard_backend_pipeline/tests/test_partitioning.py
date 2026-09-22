from datetime import datetime, timezone

from partitioning import event_partition_key, raw_object_partition, transaction_query_dimensions


def test_raw_objects_use_tenant_source_and_date_partitions():
    assert raw_object_partition("tenant-a", "bank", "2026-09-23T10:00:00Z") == "tenant=tenant-a/source=bank/year=2026/month=09/day=23"


def test_event_key_preserves_tenant_provider_and_transaction_ordering():
    assert event_partition_key({
        "tenant_id": "tenant-a",
        "source": "mpesa",
        "aggregate_id": "txn-1",
    }) == "tenant-a:mpesa:txn-1"


def test_query_dimensions_are_explicit_and_bounded():
    dimensions = transaction_query_dimensions(
        tenant_id="tenant-a",
        start=datetime(2026, 9, 1, tzinfo=timezone.utc),
        end=datetime(2026, 10, 1, tzinfo=timezone.utc),
        provider="MPESA",
    )
    assert dimensions["provider"] == "mpesa"
    assert dimensions["created_at_start"] < dimensions["created_at_end"]