from datetime import datetime, timezone

import pytest

from archival import ArchiveManager, ArchiveObjectStore, ArchivalPolicyError, RetentionPolicy


def test_archival_moves_records_to_policy_selected_warm_and_cold_tiers(tmp_path):
    manager = ArchiveManager(RetentionPolicy(hot_days=90, warm_days=730, cold_days=2555), ArchiveObjectStore(str(tmp_path)))
    transaction = {"tenant_id": "tenant-a", "transaction_id": "txn-1", "transaction_time": "2025-01-01T00:00:00Z", "amount": "5000.00"}
    now = datetime(2026, 9, 23, tzinfo=timezone.utc)
    manifest = manager.archive(transaction, now=now)
    assert manifest is not None
    assert manifest.tier == "warm"
    assert manager.store.get(manifest.object_key)


def test_archival_requires_business_approved_windows():
    with pytest.raises(ArchivalPolicyError):
        RetentionPolicy(hot_days=90, warm_days=60, cold_days=365)