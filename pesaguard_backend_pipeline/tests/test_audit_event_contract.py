import pytest

from schema_validation import SchemaValidationError, validate_audit_event


def test_audit_event_contract_accepts_actor_action_resource_and_changes():
    validate_audit_event({
        "actor": {"id": "user-1", "type": "operator"},
        "action": "transaction.status_changed",
        "resource": {"type": "transaction", "id": "tx-1"},
        "timestamp": "2026-09-23T12:00:00Z",
        "tenant_id": "tenant-a",
        "before": {"status": "PROCESSING"},
        "after": {"status": "RECONCILED"},
    })


def test_audit_event_contract_rejects_missing_actor():
    with pytest.raises(SchemaValidationError):
        validate_audit_event({
            "action": "transaction.viewed",
            "resource": {"type": "transaction", "id": "tx-1"},
            "timestamp": "2026-09-23T12:00:00Z",
        })