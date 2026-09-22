import json

import pytest

from data_catalog import CatalogError, load_catalog


def test_catalog_registers_required_assets_and_metadata():
    catalog = load_catalog()
    assert {"transactions", "reconciliation_results", "anomalies", "merchants", "customers", "audit_events", "provider_events"} <= set(catalog.assets)
    transaction = catalog.dataset("transactions")
    assert transaction.owner
    assert "transaction_id" in transaction.schema
    assert transaction.lineage
    assert transaction.consumers


def test_catalog_rejects_missing_dataset_metadata(tmp_path):
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps({"datasets": [{"name": "broken"}]}), encoding="utf-8")
    with pytest.raises(CatalogError):
        load_catalog(str(path))