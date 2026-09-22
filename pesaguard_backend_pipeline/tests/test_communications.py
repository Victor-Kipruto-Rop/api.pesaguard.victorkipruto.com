from __future__ import annotations

import hashlib
import hmac
import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from pesaguard_backend_pipeline.communications.application.notification_service import NotificationService
from pesaguard_backend_pipeline.communications.core.enums import CommunicationChannel, NotificationStatus
from pesaguard_backend_pipeline.communications.core.interfaces import NotificationRequest
from pesaguard_backend_pipeline.communications.core.exceptions import TransientCommunicationError
from pesaguard_backend_pipeline.communications.models import CommunicationAttempt, CommunicationNotification
from pesaguard_backend_pipeline.communications.providers.africas_talking import AfricasTalkingProvider
from pesaguard_backend_pipeline.communications.webhooks import process_delivery_webhook
from pesaguard_backend_pipeline.communications.events import build_notification_event, discrepancy_notification_event
from pesaguard_backend_pipeline.communications.core.state_machine import InvalidNotificationTransition, transition
from pesaguard_backend_pipeline.models import Base


class FakeAfricasTalkingClient:
    def __init__(self, result=None, error=None):
        self.result = result or {
            "status": "sent",
            "response": {"SMSMessageData": {"Recipients": [{"status": "Sent", "messageId": "AT-1"}]}},
        }
        self.error = error

    def _normalize_phone_number(self, phone):
        if phone == "0712345678":
            return "+254712345678"
        return phone

    def send_sms(self, recipient, message, idempotency_key=None):
        if self.error:
            raise self.error
        assert recipient == "+254712345678"
        assert message == "Payment received"
        assert idempotency_key == "notification-1"
        return self.result


def _session():
    engine = create_engine("sqlite://")
    import pesaguard_backend_pipeline.communications.models  # noqa: F401

    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_africas_talking_adapter_normalizes_and_returns_provider_message():
    provider = AfricasTalkingProvider(FakeAfricasTalkingClient())
    request = NotificationRequest(
        tenant_id="tenant-a",
        recipient="0712345678",
        message="Payment received",
        idempotency_key="notification-1",
    )

    result = provider.send(request)

    assert result.provider == "africas_talking"
    assert result.provider_message_id == "AT-1"
    assert result.status == "accepted"


def test_notification_service_is_tenant_scoped_and_idempotent():
    session = _session()
    service = NotificationService(session, AfricasTalkingProvider(FakeAfricasTalkingClient()))
    request = NotificationRequest(
        tenant_id="tenant-a",
        recipient="0712345678",
        message="Payment received",
        idempotency_key="notification-1",
        channel=CommunicationChannel.SMS,
    )

    first = service.send(request)
    second = service.send(request)
    session.commit()

    assert first.id == second.id
    assert session.query(CommunicationNotification).count() == 1
    assert session.query(CommunicationAttempt).count() == 1
    assert first.status == NotificationStatus.ACCEPTED.value


def test_notification_service_marks_transient_provider_failures_retryable():
    session = _session()
    service = NotificationService(
        session,
        AfricasTalkingProvider(
            FakeAfricasTalkingClient(error=TransientCommunicationError("provider timeout", code="PROVIDER_TIMEOUT"))
        ),
    )
    request = NotificationRequest(
        tenant_id="tenant-a",
        recipient="0712345678",
        message="Payment received",
        idempotency_key="notification-timeout",
    )

    notification = service.send(request)

    assert notification.status == NotificationStatus.RETRYING.value
    assert notification.failure_code == "PROVIDER_TIMEOUT"


def test_delivery_webhook_is_authenticated_and_idempotent():
    session = _session()
    service = NotificationService(session, AfricasTalkingProvider(FakeAfricasTalkingClient()))
    notification = service.send(
        NotificationRequest(
            tenant_id="tenant-a",
            recipient="0712345678",
            message="Payment received",
            idempotency_key="notification-1",
        )
    )
    session.commit()

    body = json.dumps({"id": "event-1", "messageId": "AT-1", "status": "Delivered"}).encode()
    signature = hmac.new(b"webhook-secret", body, hashlib.sha256).hexdigest()
    first = process_delivery_webhook(
        session,
        body,
        signature=signature,
        secret="webhook-secret",
    )
    session.commit()
    duplicate = process_delivery_webhook(
        session,
        body,
        signature=signature,
        secret="webhook-secret",
    )

    assert first["status"] == "processed"
    assert duplicate["status"] == "duplicate"
    assert session.get(CommunicationNotification, notification.id).status == NotificationStatus.DELIVERED.value


def test_delivery_webhook_rejects_invalid_signature():
    session = _session()
    body = b'{"id":"event-1","messageId":"AT-1","status":"Delivered"}'

    try:
        process_delivery_webhook(session, body, signature="bad", secret="webhook-secret")
    except ValueError as exc:
        assert str(exc) == "invalid webhook signature"
    else:
        raise AssertionError("invalid webhook signature was accepted")


def test_notification_events_are_versioned_and_tenant_scoped():
    event = build_notification_event(
        "fraud.suspected",
        tenant_id="tenant-a",
        context={"risk_score": 94},
        correlation_id="tx-1",
    )

    assert event["event"] == "fraud.suspected"
    assert event["tenant_id"] == "tenant-a"
    assert event["context"] == {"risk_score": 94}
    assert event["schema_version"] == 1


def test_discrepancy_event_maps_review_outcomes():
    event = discrepancy_notification_event(
        {"status": "missing_payment", "trans_id": "tx-1", "severity": "critical"},
        "tenant-a",
    )

    assert event["event"] == "reconciliation.exception_created"
    assert event["correlation_id"] == "tx-1"


def test_notification_state_machine_rejects_terminal_regression():
    assert transition("queued", "processing") == "processing"
    try:
        transition("delivered", "processing")
    except InvalidNotificationTransition:
        pass
    else:
        raise AssertionError("terminal notification transition was accepted")
