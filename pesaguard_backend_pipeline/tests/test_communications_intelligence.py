"""Intelligence and resilience tests for the hardened communications platform."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from pesaguard_backend_pipeline.communications.core.enums import CommunicationChannel, CommunicationPriority
from pesaguard_backend_pipeline.communications.core.error_categories import (
    ProviderErrorCategory,
    category_for_code,
    category_for_exception,
    failover_eligible,
)
from pesaguard_backend_pipeline.communications.core.exceptions import (
    PermanentCommunicationError,
    TransientCommunicationError,
)
from pesaguard_backend_pipeline.communications.core.interfaces import NotificationRequest, ProviderMessage
from pesaguard_backend_pipeline.communications.anomaly import classify_anomaly, detect_otp_abuse, rolling_zscore
from pesaguard_backend_pipeline.communications.cost import build_cost, estimate_segments
from pesaguard_backend_pipeline.communications.domain import OtpRateLimited, issue_otp, verify_otp
from pesaguard_backend_pipeline.communications.flags import is_enabled, snapshot
from pesaguard_backend_pipeline.communications.governor import RateGovernor
from pesaguard_backend_pipeline.communications.incidents import (
    InvalidIncidentTransition,
    report_incident,
    sla_breach,
    transition_incident,
)
from pesaguard_backend_pipeline.communications.models import (
    CommunicationIncident,
    CommunicationNotification,
    CommunicationOtpChallenge,
    CommunicationOutboxEntry,
    CommunicationSavedFilter,
    CommunicationTenantQuota,
    CommunicationWebhookEvent,
)
from pesaguard_backend_pipeline.communications.models import utc_now
from pesaguard_backend_pipeline.communications.policy import NotificationPolicyEngine
from pesaguard_backend_pipeline.communications.providers.router import CircuitBreaker, CircuitState, ProviderRouter
from pesaguard_backend_pipeline.communications.webhooks import ignore_webhook_event, process_delivery_webhook, replay_webhook_event
from pesaguard_backend_pipeline.models import Base


class StubProvider:
    def __init__(self, name: str, *, failures: int = 0, error=None):
        self.name = name
        self.supported_channels = frozenset({CommunicationChannel.SMS})
        self.failures = failures
        self.error = error

    def send(self, request):
        if self.error is not None:
            raise self.error
        if self.failures > 0:
            self.failures -= 1
            raise TransientCommunicationError("provider timed out", code="PROVIDER_TIMEOUT")
        return ProviderMessage(self.name, f"{self.name}-1", "accepted")

    def validate_recipient(self, channel, recipient):
        return recipient


def session():
    engine = create_engine("sqlite://")
    import pesaguard_backend_pipeline.communications.models  # noqa: F401

    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


# --- error classification ------------------------------------------------------

def test_error_categories_map_adapter_codes_and_gate_failover():
    assert category_for_code("PROVIDER_TIMEOUT") is ProviderErrorCategory.TIMEOUT
    assert category_for_code("PROVIDER_NOT_CONFIGURED") is ProviderErrorCategory.AUTHENTICATION_ERROR
    assert category_for_code("INVALID_RECIPIENT") is ProviderErrorCategory.INVALID_RECIPIENT
    assert category_for_exception(TransientCommunicationError("x", code="PROVIDER_TIMEOUT")) is ProviderErrorCategory.TIMEOUT
    assert failover_eligible(ProviderErrorCategory.TIMEOUT) is True
    assert failover_eligible(ProviderErrorCategory.INVALID_RECIPIENT) is False
    assert failover_eligible(ProviderErrorCategory.INSUFFICIENT_BALANCE) is False


# --- circuit breaker -------------------------------------------------------------

def test_circuit_breaker_opens_half_opens_and_closes():
    breaker = CircuitBreaker("test", failure_threshold=2, recovery_seconds=0)
    assert breaker.allow() is True
    breaker.record_failure(ProviderErrorCategory.TIMEOUT)
    assert breaker.state is CircuitState.CLOSED
    breaker.record_failure(ProviderErrorCategory.TIMEOUT)
    assert breaker.state is CircuitState.OPEN
    assert breaker.allow() is False
    assert breaker.allow() is True  # recovery_seconds=0 -> HALF_OPEN
    assert breaker.state is CircuitState.HALF_OPEN
    breaker.record_success()
    assert breaker.state is CircuitState.CLOSED
    snap = breaker.snapshot()
    assert snap["state"] == "CLOSED" and snap["provider"] == "test"


def test_router_fails_over_on_transient_but_not_permanent_errors():
    request = NotificationRequest(tenant_id="tenant-a", recipient="+254700000001", message="hi", idempotency_key="k1")
    primary = StubProvider("primary", error=TransientCommunicationError("timeout", code="PROVIDER_TIMEOUT"))
    backup = StubProvider("backup")
    router = ProviderRouter({"primary": primary, "backup": backup}, {CommunicationChannel.SMS: ["primary", "backup"]})
    assert router.send(request).provider == "backup"

    permanent_primary = StubProvider("primary", error=PermanentCommunicationError("bad number", code="INVALID_RECIPIENT"))
    router2 = ProviderRouter({"primary": permanent_primary, "backup": backup}, {CommunicationChannel.SMS: ["primary", "backup"]})
    try:
        router2.send(request)
    except PermanentCommunicationError:
        pass
    else:
        raise AssertionError("permanent error must not fail over")
    snap = router2.snapshot()
    assert snap["backup"]["state"] == "CLOSED"


# --- incidents -------------------------------------------------------------------

def test_incident_fingerprint_deduplicates_and_aggregates():
    db = session()
    now = datetime.now(timezone.utc)
    first = report_incident(
        db, category="provider", title="Africa's Talking degradation",
        fingerprint="provider_degradation_africas_talking", severity="high",
        tenant_id="tenant-a", metrics={"error_category": "TIMEOUT"}, now=now,
    )
    second = report_incident(
        db, category="provider", title="Africa's Talking degradation",
        fingerprint="provider_degradation_africas_talking", severity="high",
        tenant_id="tenant-a", metrics={"error_category": "TIMEOUT"}, now=now,
    )
    assert first.id == second.id
    assert second.occurrence_count == 2
    assert db.query(CommunicationIncident).count() == 1


def test_incident_status_workflow_is_enforced():
    db = session()
    incident = report_incident(db, category="sla", title="SLA breach", fingerprint="sla_breach_tenant-a_critical", severity="medium")
    transition_incident(db, incident, "investigating")
    assert incident.status == "investigating" and incident.acknowledged_at is not None
    transition_incident(db, incident, "mitigated")
    transition_incident(db, incident, "resolved")
    assert incident.resolved_at is not None
    try:
        transition_incident(db, incident, "investigating")
    except InvalidIncidentTransition:
        pass
    else:
        raise AssertionError("resolved -> investigating must be rejected")


# --- SLA --------------------------------------------------------------------------

def test_sla_breach_detection_uses_priority_targets():
    now = datetime.now(timezone.utc)
    assert sla_breach(now - timedelta(seconds=2), "critical") is None
    breach = sla_breach(now - timedelta(seconds=18), "critical")
    assert breach is not None and breach["target_seconds"] == 5 and breach["actual_seconds"] >= 18
    assert sla_breach(now - timedelta(seconds=10), "low") is None


# --- policy engine ------------------------------------------------------------------

def test_policy_engine_decides_channels_priorities_and_escalations():
    engine = NotificationPolicyEngine()

    small = engine.decide("transaction.completed", tenant_id="tenant-a", context={"amount": 1500})
    assert small.channels == (CommunicationChannel.SMS,) and small.priority is CommunicationPriority.NORMAL

    high_value = engine.decide("transaction.completed", tenant_id="tenant-a", context={"amount": 250_000})
    assert CommunicationChannel.VOICE in high_value.channels and high_value.priority is CommunicationPriority.HIGH

    confirmed = engine.decide("fraud.confirmed", tenant_id="tenant-a", context={"risk_score": 92})
    assert confirmed.priority is CommunicationPriority.CRITICAL and confirmed.create_incident is True

    analyst = engine.decide("reconciliation.exception_created", tenant_id="tenant-a", context={"amount": 500})
    assert analyst.template == "reconciliation.analyst_review" and analyst.priority is CommunicationPriority.NORMAL
    manager = engine.decide("reconciliation.exception_created", tenant_id="tenant-a", context={"amount": 5_000})
    assert manager.template == "reconciliation.manager_review"
    executive = engine.decide("reconciliation.exception_created", tenant_id="tenant-a", context={"amount": 500_000})
    assert executive.priority is CommunicationPriority.CRITICAL and executive.create_incident is True


def test_policy_quiet_hours_defers_normal_but_not_critical():
    quiet_config = {"quiet_hours_start": "22:00", "quiet_hours_end": "06:00", "quiet_hours_timezone": "UTC"}
    engine = NotificationPolicyEngine(now=datetime(2026, 9, 8, 23, 0, tzinfo=timezone.utc))

    normal = engine.decide("transaction.failed", tenant_id="tenant-a", tenant_config=quiet_config, context={})
    assert normal.quiet_hours_deferred is True and normal.delay_until is not None
    assert normal.delay_until.hour == 6

    critical = engine.decide("fraud.confirmed", tenant_id="tenant-a", tenant_config=quiet_config, context={"risk_score": 95})
    assert critical.quiet_hours_deferred is False and critical.delay_until is None


# --- cost engine -------------------------------------------------------------------

def test_segment_estimation_and_cost_build_are_accurate():
    assert estimate_segments("x" * 160) == 1
    assert estimate_segments("x" * 161) == 2
    assert estimate_segments("é" * 70) == 1
    assert estimate_segments("é" * 71) == 2
    cost = build_cost(CommunicationChannel.SMS, "x" * 340)
    assert cost["segments"] == 3 and cost["total_cost"] > 0 and cost["currency"] == "KES"


# --- anomaly detection -----------------------------------------------------------

def test_rolling_zscore_and_classification_detect_spikes():
    baseline = [100.0] * 20 + [104.0, 96.0]
    assert classify_anomaly(rolling_zscore(baseline, 420.0), sensitivity=3.0) == "spike"
    assert classify_anomaly(rolling_zscore(baseline, 100.0), sensitivity=3.0) is None
    assert classify_anomaly(rolling_zscore(baseline, 5.0), sensitivity=3.0) == "drop"


def test_otp_abuse_detection_flags_recipient_flood_and_ip_enumeration():
    db = session()
    now = datetime.now(timezone.utc)
    for _ in range(7):
        db.add(CommunicationOtpChallenge(
            id=f"otp_{os.urandom(8).hex()}",
            tenant_id="tenant-a", recipient="+254700000001", purpose="login",
            code_hash="x" * 64, expires_at=now + timedelta(minutes=5), created_at=now - timedelta(minutes=1),
        ))
    for index in range(25):
        db.add(CommunicationOtpChallenge(
            id=f"otp_{os.urandom(8).hex()}",
            tenant_id="tenant-a", recipient=f"+254700000{index:05d}", purpose="login",
            code_hash="x" * 64, expires_at=now + timedelta(minutes=5), ip_address="203.0.113.9", created_at=now - timedelta(minutes=1),
        ))
    db.commit()
    findings = detect_otp_abuse(db, window_minutes=60, now=now)
    types = {finding["type"] for finding in findings}
    assert "otp_flood_same_recipient" in types
    assert "otp_enumeration_same_ip" in types


# --- OTP hardening -----------------------------------------------------------------

def test_otp_issue_verify_cooldown_and_attempt_limits():
    db = session()
    now = datetime.now(timezone.utc)
    challenge, code = issue_otp(db, tenant_id="tenant-a", recipient="+254700000002", purpose="login", now=now)
    assert challenge.max_attempts == 5 and challenge.code_hash != code
    assert verify_otp(db, challenge, "000000", now=now) is False
    assert verify_otp(db, challenge, code, now=now) is True
    assert verify_otp(db, challenge, code, now=now) is False  # consumed
    try:
        issue_otp(db, tenant_id="tenant-a", recipient="+254700000002", purpose="login", now=now + timedelta(seconds=10))
    except OtpRateLimited as exc:
        assert exc.reason == "resend_cooldown"
    else:
        raise AssertionError("resend cooldown was not enforced")


# --- rate governor + flags -----------------------------------------------------------

def test_rate_governor_enforces_bucket_and_backpressure():
    governor = RateGovernor(provider_rates={"africas_talking": 2}, queue_depth=0)
    assert governor.acquire("africas_talking") is True
    assert governor.acquire("africas_talking") is True
    assert governor.acquire("africas_talking") is False
    assert governor.wait_seconds("africas_talking") > 0
    deep = RateGovernor(queue_depth=10)
    assert deep.acquire("any", queue_depth=50) is False
    assert deep.acquire("any", queue_depth=5) is True


def test_feature_flags_default_and_env_override(monkeypatch):
    monkeypatch.delenv("PESAGUARD_FLAG_AFRICASTALKING_SMS", raising=False)
    assert is_enabled("AFRICASTALKING_SMS") is True
    assert is_enabled("AFRICASTALKING_VOICE") is False
    monkeypatch.setenv("PESAGUARD_FLAG_AFRICASTALKING_VOICE", "true")
    assert is_enabled("AFRICASTALKING_VOICE") is True
    assert "PROVIDER_FAILOVER" in snapshot()


# --- webhook replay protection + inbox ---------------------------------------------

def _notification_with_provider_message(db, provider_message_id="AT-1"):
    notification = CommunicationNotification(
        id=f"notification_{os.urandom(8).hex()}",
        tenant_id="tenant-a", channel="sms", recipient="+254700000001",
        message="Payment received", priority="normal", status="submitted",
        idempotency_key=f"idemp-{os.urandom(4).hex()}", provider="africas_talking",
        provider_message_id=provider_message_id,
        created_at=datetime.now(timezone.utc) - timedelta(seconds=2),
        submitted_at=datetime.now(timezone.utc) - timedelta(seconds=1),
    )
    db.add(notification)
    db.flush()
    return notification


def _signed(body: bytes, secret="webhook-secret"):
    import hashlib
    import hmac

    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_webhook_replay_protection_rejects_stale_timestamps():
    db = session()
    stale = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    body = f'{{"id": "event-old", "messageId": "AT-1", "status": "Delivered", "timestamp": "{stale}"}}'.encode()
    try:
        process_delivery_webhook(db, body, signature=_signed(body), secret="webhook-secret")
    except ValueError as exc:
        assert "too old" in str(exc)
    else:
        raise AssertionError("stale webhook timestamp was accepted")


def test_unknown_notification_webhook_is_stored_for_replay_not_rejected():
    db = session()
    body = b'{"id": "event-unknown", "messageId": "AT-UNKNOWN", "status": "Delivered"}'
    result = process_delivery_webhook(db, body, signature=_signed(body), secret="webhook-secret")
    assert result["status"] == "pending_review"
    stored = db.query(CommunicationWebhookEvent).filter_by(provider_event_id="event-unknown").one()
    assert stored.processing_status == "unprocessed" and stored.tenant_id is None
    replay = replay_webhook_event(db, stored.id)
    assert replay["status"] == "unresolved"


def test_webhook_processing_records_payload_hash_and_inbox_status():
    db = session()
    notification = _notification_with_provider_message(db, "AT-2")
    body = b'{"id": "event-2", "messageId": "AT-2", "status": "Delivered"}'
    result = process_delivery_webhook(db, body, signature=_signed(body), secret="webhook-secret")
    assert result["status"] == "processed"
    event = db.query(CommunicationWebhookEvent).filter_by(provider_event_id="event-2").one()
    assert event.processing_status == "processed" and len(event.payload_hash) == 64
    assert notification.status == "delivered" and notification.delivered_at is not None
    ignored = ignore_webhook_event(db, event.id)
    assert ignored["status"] == "ignored"


# --- worker error classification ------------------------------------------------------

def test_worker_classifies_errors_and_schedules_retry():
    from pesaguard_backend_pipeline.communications.application.notification_service import NotificationService
    from pesaguard_backend_pipeline.communications.worker import process_outbox_once

    db = session()
    service = NotificationService(db, StubProvider("africas_talking"))
    notification = service.enqueue(NotificationRequest(
        tenant_id="tenant-a", recipient="+254700000003", message="hello",
        idempotency_key="worker-classify-1", channel=CommunicationChannel.SMS,
        priority=CommunicationPriority.NORMAL,
    ))
    db.commit()

    class FailingProvider(StubProvider):
        def send(self, request):
            raise TransientCommunicationError("provider timed out", code="PROVIDER_TIMEOUT")

    process_outbox_once(db, provider_factory=lambda: FailingProvider("africas_talking"), worker_id="w1", publish_events=False)
    db.commit()
    from pesaguard_backend_pipeline.communications.models import CommunicationAttempt

    attempt = db.query(CommunicationAttempt).order_by(CommunicationAttempt.id.desc()).first()
    assert attempt.error_category == "TIMEOUT" and attempt.cost is not None
    entry = db.query(CommunicationOutboxEntry).filter_by(notification_id=notification.id).one()
    assert entry.status == "retrying"
    # Compare datetimes as offset-naive (SQLite strips tz info)
    assert entry.available_at.replace(tzinfo=timezone.utc) > utc_now()
    refreshed = db.query(CommunicationNotification).filter_by(id=notification.id).one()
    assert refreshed.status == "retrying" and refreshed.queued_at is not None
    db.close()


# --- persisted product models ----------------------------------------------------------

def test_saved_filters_and_quotas_persist_per_tenant():
    db = session()
    db.add(CommunicationSavedFilter(id="sf1", tenant_id="tenant-a", name="Failed SMS today", query={"status": "failed", "channel": "sms"}))
    db.add(CommunicationTenantQuota(id="q1", tenant_id="tenant-a", scope="sms_daily", limit_value=10000))
    db.add(CommunicationSavedFilter(id="sf2", tenant_id="tenant-b", name="Failed SMS today", query={"status": "failed"}))
    db.commit()
    assert db.query(CommunicationSavedFilter).filter_by(tenant_id="tenant-a").count() == 1
    assert db.query(CommunicationSavedFilter).filter_by(name="Failed SMS today").count() == 2
    assert db.query(CommunicationTenantQuota).filter_by(tenant_id="tenant-a", scope="sms_daily").one().limit_value == 10000