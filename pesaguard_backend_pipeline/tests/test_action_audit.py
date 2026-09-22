import pytest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from pesaguard_backend_pipeline.action_audit import (
    ActionAuditEntry,
    ActionAuditRecord,
    AuditDeliveryStatus,
    AuditPrivacySettings,
    AuditRetentionPolicy,
    AuditSigner,
    Base,
    can_access_audit_tenant,
    deliver_audit_outbox,
    get_audit_delivery_metrics,
    get_audit_operations_dashboard,
    build_siem_event,
    deliver_audit_to_siem,
    export_audit_to_immutable_storage,
    FileImmutableAuditStore,
    persist_audit_event,
    place_audit_legal_hold,
    privacy_safe_audit_dict,
    query_audit_entries,
    record_audit_log_access,
    set_audit_privacy_settings,
    set_audit_retention_policy,
    list_audit_retention_candidates,
    recover_stale_audit_deliveries,
    verify_audit_integrity,
    MAX_LIST_ITEMS,
    MAX_STRING_LENGTH,
    build_audit_entry,
)


def test_action_audit_record_is_frozen():
    record = ActionAuditRecord("tenant-a", "system", "created")
    with pytest.raises(AttributeError):
        record.action = "changed"


def test_detail_values_are_redacted_and_bounded():
    entry = build_audit_entry(
        ActionAuditRecord(
            " tenant-a ",
            " system ",
            " created ",
            {"Authorization": "Bearer secret", "nested": {"token": "secret"}},
        )
    )
    assert entry["tenant_id"] == "tenant-a"
    assert entry["details"]["Authorization"] == "[REDACTED]"
    assert entry["details"]["nested"]["token"] == "[REDACTED]"

    with pytest.raises(ValueError):
        build_audit_entry(ActionAuditRecord("tenant-a", "system", "created", {"x": "a" * (MAX_STRING_LENGTH + 1)}))
    with pytest.raises(ValueError):
        build_audit_entry(ActionAuditRecord("tenant-a", "system", "created", {"x": list(range(MAX_LIST_ITEMS + 1))}))


def test_detail_values_must_be_json_serializable():
    with pytest.raises(ValueError, match="JSON-serializable"):
        build_audit_entry(ActionAuditRecord("tenant-a", "system", "created", {"value": object()}))


def test_audit_entries_are_append_only_after_insert():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    entry = ActionAuditEntry(tenant_id="tenant-a", actor="system", action="created", details={})
    session.add(entry)
    session.commit()

    with pytest.raises(ValueError, match="cannot be updated"):
        entry.action = "changed"

    session.delete(entry)
    with pytest.raises(ValueError, match="cannot be deleted"):
        session.commit()


def test_audit_entries_are_append_only_at_database_boundary():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    entry = ActionAuditEntry(tenant_id="tenant-a", actor="system", action="created", details={})
    session.add(entry)
    session.commit()

    with pytest.raises(Exception, match="append-only"):
        session.execute(
            ActionAuditEntry.__table__.update()
            .where(ActionAuditEntry.id == entry.id)
            .values(actor="tampered")
        )
        session.commit()
    session.rollback()

    with pytest.raises(Exception, match="append-only"):
        session.execute(
            ActionAuditEntry.__table__.delete()
            .where(ActionAuditEntry.id == entry.id)
        )
        session.commit()


def test_structured_audit_fields_and_canonical_actions():
    entry = build_audit_entry(ActionAuditRecord(
        "tenant-a",
        "user-1",
        "create_webhook",
        category="configuration",
        outcome="success",
        severity="notice",
        resource_type="webhook",
        resource_id="hook-1",
        request_id="req-1",
        trace_id="trace-1",
        correlation_id="corr-1",
    ))
    assert entry["action"] == "webhook.created"
    assert entry["category"] == "configuration"
    assert entry["resource_id"] == "hook-1"


def test_audit_query_is_tenant_scoped_and_filterable():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add_all([
        ActionAuditEntry(
            tenant_id="tenant-a", actor="user-1", action="create_webhook",
            category="configuration", resource_type="webhook", resource_id="hook-1",
            trace_id="trace-1", details={},
        ),
        ActionAuditEntry(tenant_id="tenant-b", actor="user-2", action="created", details={}),
    ])
    session.commit()

    principal = type("Principal", (), {"tenant_id": "tenant-a", "permissions": []})()
    rows = query_audit_entries(
        session,
        principal,
        "tenant-a",
        action="webhook.created",
        resource_type="webhook",
        trace_id="trace-1",
    )
    assert len(rows) == 1
    assert rows[0].tenant_id == "tenant-a"
    assert can_access_audit_tenant(principal, "tenant-b") is False
    with pytest.raises(PermissionError):
        query_audit_entries(session, principal, "tenant-b")


def test_audit_write_is_idempotent_and_creates_outbox_atomically():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    record = ActionAuditRecord("tenant-a", "user-1", "configuration.updated", request_id="req-1")

    first, first_outbox, created = persist_audit_event(session, record)
    session.commit()
    second, second_outbox, duplicate = persist_audit_event(session, record)

    assert created is True
    assert duplicate is False
    assert first.id == second.id
    assert first_outbox.id == second_outbox.id
    assert session.query(ActionAuditEntry).count() == 1


def test_audit_delivery_retries_then_dead_letters_and_recovers_claims():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    _, outbox, _ = persist_audit_event(
        session,
        ActionAuditRecord("tenant-a", "worker", "configuration.updated", request_id="req-2"),
        max_attempts=2,
    )
    session.commit()
    now = datetime.now(timezone.utc)

    def fail(_payload):
        raise RuntimeError("downstream unavailable")

    assert deliver_audit_outbox(session, fail, now=now)["retried"] == 1
    outbox.next_attempt_at = now
    session.commit()
    assert deliver_audit_outbox(session, fail, now=now)["dead_lettered"] == 1
    assert session.get(type(outbox), outbox.id).status == AuditDeliveryStatus.DEAD_LETTER.value

    _, stale, _ = persist_audit_event(
        session,
        ActionAuditRecord("tenant-a", "worker", "configuration.updated", request_id="req-3"),
    )
    stale.status = AuditDeliveryStatus.IN_PROGRESS.value
    stale.locked_at = now - timedelta(hours=1)
    session.commit()
    assert recover_stale_audit_deliveries(session, now=now, lock_timeout=timedelta(minutes=10)) == 1
    assert session.get(type(stale), stale.id).status == AuditDeliveryStatus.FAILED.value


def test_audit_delivery_metrics_are_tenant_authorized():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    persist_audit_event(session, ActionAuditRecord("tenant-a", "worker", "configuration.updated", request_id="req-4"))
    session.commit()
    principal = type("Principal", (), {"tenant_id": "tenant-a", "permissions": []})()

    metrics = get_audit_delivery_metrics(session, principal, "tenant-a")
    assert metrics.pending == 1
    assert metrics.delivered == 0
    with pytest.raises(PermissionError):
        get_audit_delivery_metrics(session, principal, "tenant-b")


def test_signed_chain_detects_tampering_and_exports_immutably(tmp_path: Path):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    private_key = Ed25519PrivateKey.generate()
    signer = AuditSigner(private_key, "test-key")
    principal = type("Principal", (), {"tenant_id": "tenant-a", "permissions": []})()

    persist_audit_event(
        session,
        ActionAuditRecord("tenant-a", "user-1", "configuration.updated", request_id="signed-1"),
        signer=signer,
    )
    persist_audit_event(
        session,
        ActionAuditRecord("tenant-a", "user-1", "configuration.updated", request_id="signed-2"),
        signer=signer,
    )
    session.commit()
    public_key = private_key.public_key()
    report = verify_audit_integrity(session, principal, "tenant-a", public_key=public_key)
    assert report.checked == 2
    assert report.valid == 2
    assert report.first_invalid_id is None

    first = session.query(ActionAuditEntry).order_by(ActionAuditEntry.created_at.asc()).first()
    with pytest.raises(Exception, match="append-only"):
        session.execute(
            ActionAuditEntry.__table__.update()
            .where(ActionAuditEntry.id == first.id)
            .values(actor="tampered")
        )
        session.commit()
    session.rollback()

    report = verify_audit_integrity(session, principal, "tenant-a", public_key=public_key)
    assert report.valid == 2
    store = FileImmutableAuditStore(tmp_path)
    exported = export_audit_to_immutable_storage(
        session, principal, "tenant-a", store, "tenant-a-audit.jsonl", public_key=public_key
    )
    assert exported["record_count"] == 2
    with pytest.raises(FileExistsError):
        export_audit_to_immutable_storage(
            session, principal, "tenant-a", store, "tenant-a-audit.jsonl", public_key=public_key
        )
    siem_event = build_siem_event(session.query(ActionAuditEntry).first().to_dict())
    assert siem_event["event"]["dataset"] == "pesaguard.audit"
    delivered_events = []
    result = deliver_audit_to_siem(
        session,
        principal,
        "tenant-a",
        delivered_events.append,
    )
    assert result["delivered"] == 2
    assert all(event["service"]["tenant_id"] == "tenant-a" for event in delivered_events)


def test_retention_holds_privacy_and_access_auditing():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    principal = type(
        "Principal",
        (),
        {"tenant_id": "tenant-a", "permissions": ["manage:settings"], "user_id": "admin-1", "roles": []},
    )()
    set_audit_retention_policy(session, principal, "tenant-a", 1)
    set_audit_privacy_settings(session, principal, "tenant-a", include_details=False)
    old = datetime.now(timezone.utc) - timedelta(days=3)
    audit = ActionAuditEntry(
        tenant_id="tenant-a",
        actor="alice@example.com",
        action="configuration.updated",
        details={"password": "secret", "safe": "hidden"},
        resource_type="customer",
        resource_id="customer-1",
        request_id="privacy-request",
        created_at=old,
    )
    session.add(audit)
    session.commit()
    hold = place_audit_legal_hold(session, principal, "tenant-a", "regulatory investigation", scope_type="resource", scope_id="customer-1")
    session.commit()
    assert list_audit_retention_candidates(session, principal, "tenant-a") == []
    release_id = hold.id
    from pesaguard_backend_pipeline.action_audit import release_audit_legal_hold
    release_audit_legal_hold(session, principal, release_id)
    session.commit()
    assert len(list_audit_retention_candidates(session, principal, "tenant-a")) == 1

    settings = session.query(AuditPrivacySettings).filter_by(tenant_id="tenant-a").one()
    safe = privacy_safe_audit_dict(audit, settings)
    assert safe["actor"] != "alice@example.com"
    assert safe["resource_id"] != "customer-1"
    assert safe["details"] == {}

    record_audit_log_access(session, principal, "tenant-a", filters={"request_id": "privacy-request"})
    session.commit()
    dashboard = get_audit_operations_dashboard(session, principal, "tenant-a")
    assert dashboard.tenant_id == "tenant-a"
    assert dashboard.active_legal_holds == 0
    assert any(alert["code"] == "audit_unprotected_legacy_rows" for alert in dashboard.alerts)
