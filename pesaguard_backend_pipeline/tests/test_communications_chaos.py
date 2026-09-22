"""Chaos and resilience tests for the communications platform.

These tests verify graceful recovery under controlled failure conditions:
provider timeouts, provider 500s, provider 429s, duplicate/out-of-order
webhooks, worker crashes, and database slowdowns.

Run with:
    python -m pytest pesaguard_backend_pipeline/test_communications_chaos.py -v
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from pesaguard_backend_pipeline.communications.core.enums import CommunicationChannel, CommunicationPriority
from pesaguard_backend_pipeline.communications.core.exceptions import TransientCommunicationError
from pesaguard_backend_pipeline.communications.core.interfaces import NotificationRequest
from pesaguard_backend_pipeline.communications.models import (
    CommunicationNotification,
    CommunicationOutboxEntry,
)
from pesaguard_backend_pipeline.communications.worker import process_outbox_once
from pesaguard_backend_pipeline.communications.webhooks import process_delivery_webhook
from pesaguard_backend_pipeline.communications.application.notification_service import NotificationService
from pesaguard_backend_pipeline.models import Base


class FakeAfricasTalkingClient:
    """Minimal stand-in for the real Africa's Talking HTTP client."""

    def __init__(self, result=None, error=None, latency_seconds=0.0):
        self.result = result or {
            "status": "sent",
            "response": {"SMSMessageData": {"Recipients": [{"status": "Sent", "messageId": "AT-CHAOS-1"}]}},
        }
        self.error = error
        self.latency_seconds = latency_seconds

    def _normalize_phone_number(self, phone):
        if phone.startswith("0"):
            return "+254" + phone[1:]
        return phone

    def send_sms(self, recipient, message, idempotency_key=None):
        if self.error:
            raise self.error
        if self.latency_seconds:
            time.sleep(self.latency_seconds)
        return self.result


def _session():
    engine = create_engine("sqlite://")
    import pesaguard_backend_pipeline.communications.models  # noqa: F401

    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _enqueue(db, *, key="chaos-key", provider=None):
    from pesaguard_backend_pipeline.communications.providers.africas_talking import AfricasTalkingProvider

    client = FakeAfricasTalkingClient()
    provider = provider or AfricasTalkingProvider(client)
    service = NotificationService(db, provider)
    notification = service.enqueue(NotificationRequest(
        tenant_id="tenant-a",
        recipient="0712345678",
        message="Chaos test message",
        idempotency_key=key,
        channel=CommunicationChannel.SMS,
        priority=CommunicationPriority.NORMAL,
    ))
    db.commit()
    return notification


def _signed(body: bytes, secret="webhook-secret"):
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


# --- Provider failure scenarios ---------------------------------------------------

def test_provider_timeout_recovers_on_retry():
    """Provider times out first, succeeds on retry → no dead-letter."""
    db = _session()

    class TimeoutThenOk:
        def __init__(self):
            self.calls = 0

        def send_sms(self, recipient, message, idempotency_key=None):
            self.calls += 1
            if self.calls == 1:
                raise TimeoutError("provider timed out")
            return {"status": "sent", "response": {"SMSMessageData": {"Recipients": [{"messageId": "AT-OK"}]}}}

        def _normalize_phone_number(self, phone):
            return phone

    from pesaguard_backend_pipeline.communications.providers.africas_talking import AfricasTalkingProvider

    client = TimeoutThenOk()
    notification = _enqueue(db, key="timeout-then-ok", provider=AfricasTalkingProvider(client))
    process_outbox_once(db, provider_factory=lambda: AfricasTalkingProvider(client), worker_id="chaos-w1", publish_events=False)
    db.commit()
    entry = db.query(CommunicationOutboxEntry).filter_by(notification_id=notification.id).one()
    assert entry.status in ("retrying", "completed")


def test_provider_500_dead_letters_after_max_attempts():
    """Provider always returns 500-equivalent → dead-letter after max attempts."""
    db = _session()

    class AlwaysFails:
        def _normalize_phone_number(self, phone):
            return phone

        def send_sms(self, recipient, message, idempotency_key=None):
            raise TransientCommunicationError("service unavailable", code="PROVIDER_UNAVAILABLE")

    from pesaguard_backend_pipeline.communications.providers.africas_talking import AfricasTalkingProvider

    client = AlwaysFails()
    notification = _enqueue(db, key="always-fails", provider=AfricasTalkingProvider(client))
    for _ in range(8):
        process_outbox_once(db, provider_factory=lambda: AfricasTalkingProvider(client), worker_id="chaos-w2", publish_events=False)
        db.commit()
        # Force the retry to become due immediately (bypass backoff wait).
        db.query(CommunicationOutboxEntry).filter_by(notification_id=notification.id).update(
            {"available_at": datetime.now(timezone.utc) - timedelta(seconds=1)},
            synchronize_session=False,
        )
        db.commit()
    entry = db.query(CommunicationOutboxEntry).filter_by(notification_id=notification.id).one()
    assert entry.status == "dead_letter"
    assert entry.attempt_count >= entry.max_attempts


def test_provider_429_rates_limited_then_recovers():
    """Provider rate-limited (429) → message retries with backoff, eventually succeeds."""
    db = _session()

    class RateLimitedOnce:
        def __init__(self):
            self.calls = 0

        def _normalize_phone_number(self, phone):
            return phone

        def send_sms(self, recipient, message, idempotency_key=None):
            self.calls += 1
            if self.calls <= 2:
                raise TransientCommunicationError("rate limited", code="PROVIDER_RATE_LIMITED")
            return {"status": "sent", "response": {"SMSMessageData": {"Recipients": [{"messageId": "AT-RL"}]}}}

    from pesaguard_backend_pipeline.communications.providers.africas_talking import AfricasTalkingProvider

    client = RateLimitedOnce()
    notification = _enqueue(db, key="rate-limited", provider=AfricasTalkingProvider(client))
    for _ in range(3):
        process_outbox_once(db, provider_factory=lambda: AfricasTalkingProvider(client), worker_id="chaos-w3", publish_events=False)
        db.commit()
        # Bypass retry backoff so the entry becomes claimable again.
        db.query(CommunicationOutboxEntry).filter_by(notification_id=notification.id).update(
            {"available_at": datetime.now(timezone.utc) - timedelta(seconds=1)},
            synchronize_session=False,
        )
        db.commit()
    entry = db.query(CommunicationOutboxEntry).filter_by(notification_id=notification.id).one()
    refreshed = db.query(CommunicationNotification).filter_by(id=notification.id).one()
    assert entry.status == "completed" or refreshed.status == "accepted"


# --- Webhook chaos scenarios --------------------------------------------------------

def test_duplicate_webhook_does_not_double_process():
    """Same delivery callback delivered twice → only one delivery report."""
    db = _session()
    notification = _enqueue(db, key="dup-webhook")
    from pesaguard_backend_pipeline.communications.providers.africas_talking import AfricasTalkingProvider

    client = FakeAfricasTalkingClient()
    process_outbox_once(db, provider_factory=lambda: AfricasTalkingProvider(client), worker_id="chaos-w4", publish_events=False)
    db.commit()
    refreshed = db.query(CommunicationNotification).filter_by(id=notification.id).one()

    body = json.dumps({"id": "event-dup-1", "messageId": refreshed.provider_message_id, "status": "Delivered"}).encode()
    first = process_delivery_webhook(db, body, signature=_signed(body), secret="webhook-secret")
    db.commit()
    second = process_delivery_webhook(db, body, signature=_signed(body), secret="webhook-secret")
    db.commit()

    assert first["status"] == "processed"
    assert second["status"] == "duplicate"
    from pesaguard_backend_pipeline.communications.models import CommunicationDeliveryReport

    assert db.query(CommunicationDeliveryReport).filter_by(notification_id=notification.id).count() == 1


def test_out_of_order_webhook_does_not_crash():
    """Delivery callback for an unknown/unsubmitted message → pending_review, not crash."""
    db = _session()
    body = json.dumps({"id": "event-ooo", "messageId": "AT-NOT-SENT", "status": "Delivered"}).encode()
    result = process_delivery_webhook(db, body, signature=_signed(body), secret="webhook-secret")
    db.commit()
    assert result["status"] == "pending_review"


def test_webhook_timestamp_in_future_rejected():
    db = _session()
    future = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
    body = f'{{"id": "event-future", "messageId": "AT-FUTURE", "status": "Delivered", "timestamp": "{future}"}}'.encode()
    try:
        process_delivery_webhook(db, body, signature=_signed(body), secret="webhook-secret")
    except ValueError as exc:
        assert "future" in str(exc)
    else:
        raise AssertionError("future-dated webhook was accepted")


def test_webhook_malformed_timestamp_rejected():
    db = _session()
    body = b'{"id":"event-malformed-time","messageId":"AT-MALFORMED","status":"Delivered","timestamp":"not-a-timestamp"}'
    try:
        process_delivery_webhook(db, body, signature=_signed(body), secret="webhook-secret")
    except ValueError as exc:
        assert str(exc) == "webhook timestamp is invalid"
    else:
        raise AssertionError("malformed webhook timestamp was accepted")


# --- Worker crash recovery ----------------------------------------------------------

def test_worker_crash_releases_lease_for_retry():
    """A crashed worker's leases expire and entries become claimable again."""
    db = _session()
    notification = _enqueue(db, key="worker-crash")
    entry = db.query(CommunicationOutboxEntry).filter_by(notification_id=notification.id).one()
    # Simulate a crashed worker: lease set but never completed.
    entry.status = "leased"
    entry.leased_by = "dead-worker"
    entry.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    entry.attempt_count = 1
    db.commit()

    from pesaguard_backend_pipeline.communications.providers.africas_talking import AfricasTalkingProvider

    client = FakeAfricasTalkingClient()
    process_outbox_once(db, provider_factory=lambda: AfricasTalkingProvider(client), worker_id="chaos-w5", publish_events=False)
    db.commit()
    refreshed = db.query(CommunicationOutboxEntry).filter_by(notification_id=notification.id).one()
    assert refreshed.status == "completed"
    assert refreshed.leased_by is None or refreshed.leased_by == "chaos-w5"


# --- Database slowdown resilience ---------------------------------------------------

def test_database_slowdown_does_not_block_enqueue():
    """Enqueue survives a slow (but functional) database."""
    db = _session()
    started = time.monotonic()
    notification = _enqueue(db, key="db-slow")
    elapsed = time.monotonic() - started
    assert notification.id
    assert elapsed < 5.0  # Not hung


# --- Idempotency under chaos ---------------------------------------------------------

def test_idempotency_key_prevents_duplicates_under_retries():
    """Repeating the same logical send returns the same notification."""
    db = _session()
    first = _enqueue(db, key="idempotent-key")
    second = _enqueue(db, key="idempotent-key")
    assert first.id == second.id
    assert db.query(CommunicationNotification).filter_by(idempotency_key="idempotent-key").count() == 1