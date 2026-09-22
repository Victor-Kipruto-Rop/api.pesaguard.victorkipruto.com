from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from ..core.interfaces import CommunicationProvider, NotificationRequest
from ..core.exceptions import CommunicationError
from ..core.enums import NotificationStatus
from ..models import CommunicationAttempt, CommunicationNotification
from ..models import CommunicationConsent, CommunicationPreference
from ..domain import is_allowed_now
from ..outbox import enqueue_notification
from ..core.state_machine import transition


class NotificationService:
    """Persist and submit one notification through an injected provider."""

    def __init__(self, session: Session, provider: CommunicationProvider):
        self.session = session
        self.provider = provider

    def enqueue(self, request: NotificationRequest, *, cost: dict[str, Any] | None = None, latency_ms: int | None = None) -> CommunicationNotification:
        """Persist a notification and outbox entry without contacting a provider."""
        if not request.idempotency_key:
            raise ValueError("idempotency_key is required for notification delivery")
        purpose = str(request.variables.get("purpose", "transactional"))
        if purpose == "marketing":
            consent = self.session.query(CommunicationConsent).filter_by(
                tenant_id=request.tenant_id, recipient=request.recipient, channel=request.channel.value, granted=1,
            ).one_or_none()
            if consent is None:
                raise ValueError("marketing consent is required for this recipient")
            preference = self.session.query(CommunicationPreference).filter_by(
                tenant_id=request.tenant_id, recipient=request.recipient,
            ).one_or_none()
            if not is_allowed_now(preference):
                raise ValueError("recipient is currently in quiet hours")
        existing = self.session.query(CommunicationNotification).filter_by(
            tenant_id=request.tenant_id,
            idempotency_key=request.idempotency_key,
        ).one_or_none()
        if existing is not None:
            enqueue_notification(self.session, existing)
            return existing
        metadata = dict(request.variables)
        if cost is not None:
            metadata.setdefault("email_cost", cost)
        if latency_ms is not None:
            metadata.setdefault("email_latency_ms", latency_ms)
        notification = CommunicationNotification(
            id=request.notification_id or f"notification_{uuid.uuid4().hex}",
            tenant_id=request.tenant_id,
            channel=request.channel.value,
            recipient=self.provider.validate_recipient(request.channel, request.recipient),
            message=request.message,
            template_id=request.template_id,
            priority=request.priority.value,
            status=NotificationStatus.QUEUED.value,
            idempotency_key=request.idempotency_key,
            provider=self.provider.name,
            correlation_id=request.correlation_id,
            trace_id=request.trace_id,
            metadata_json=metadata,
        )
        self.session.add(notification)
        self.session.flush()
        notification.status = transition(notification.status, NotificationStatus.QUEUED)
        enqueue_notification(self.session, notification)
        return notification

    def send(self, request: NotificationRequest, *, cost: dict[str, Any] | None = None, latency_ms: int | None = None) -> CommunicationNotification:
        if not request.idempotency_key:
            raise ValueError("idempotency_key is required for notification delivery")
        existing = self.session.query(CommunicationNotification).filter_by(
            tenant_id=request.tenant_id,
            idempotency_key=request.idempotency_key,
        ).one_or_none()
        if existing is not None:
            return existing

        started_at = datetime.now(timezone.utc)
        metadata = dict(request.variables)
        if cost is not None:
            metadata.setdefault("email_cost", cost)
        if latency_ms is not None:
            metadata.setdefault("email_latency_ms", latency_ms)

        notification = CommunicationNotification(
            id=request.notification_id or f"notification_{uuid.uuid4().hex}",
            tenant_id=request.tenant_id,
            channel=request.channel.value,
            recipient=request.recipient,
            message=request.message,
            template_id=request.template_id,
            priority=request.priority.value,
            status=NotificationStatus.CREATED.value,
            idempotency_key=request.idempotency_key,
            provider=self.provider.name,
            correlation_id=request.correlation_id,
            trace_id=request.trace_id,
            metadata_json=metadata,
        )
        self.session.add(notification)
        self.session.flush()
        notification.status = transition(notification.status, NotificationStatus.QUEUED)
        notification.status = transition(notification.status, NotificationStatus.PROCESSING)
        attempt = CommunicationAttempt(
            id=f"attempt_{uuid.uuid4().hex}",
            notification_id=notification.id,
            attempt_number=1,
            provider=self.provider.name,
            status=NotificationStatus.PROCESSING.value,
            started_at=started_at,
            cost=cost or None,
            latency_ms=latency_ms,
        )
        self.session.add(attempt)
        try:
            result = self.provider.send(request)
            elapsed_ms = int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000)
            final_latency_ms = latency_ms if latency_ms is not None else elapsed_ms
            notification.status = transition(notification.status, result.status)
            notification.provider_message_id = result.provider_message_id
            attempt.status = result.status
            attempt.provider_message_id = result.provider_message_id
            attempt.latency_ms = final_latency_ms
            attempt.cost = cost or attempt.cost
            attempt.completed_at = datetime.now(timezone.utc)
            notification.metadata_json = {
                **dict(notification.metadata_json or {}),
                "provider_response": dict(result.raw_response),
                "email_cost": cost,
                "email_latency_ms": final_latency_ms,
            }
        except CommunicationError as exc:
            elapsed_ms = int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000)
            final_latency_ms = latency_ms if latency_ms is not None else elapsed_ms
            target_status = NotificationStatus.RETRYING if exc.retryable else NotificationStatus.FAILED
            notification.status = transition(notification.status, target_status)
            notification.failure_code = exc.code
            notification.failure_reason = str(exc)
            attempt.status = notification.status
            attempt.error_code = exc.code
            attempt.error_detail = str(exc)
            attempt.latency_ms = final_latency_ms
            attempt.cost = cost or attempt.cost
            attempt.completed_at = datetime.now(timezone.utc)
            notification.metadata_json = {
                **dict(notification.metadata_json or {}),
                "email_cost": cost,
                "email_latency_ms": final_latency_ms,
                "last_provider_error": exc.code,
            }
        self.session.flush()
        return notification
