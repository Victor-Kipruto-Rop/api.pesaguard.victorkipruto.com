from __future__ import annotations

import hashlib
import hmac
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Mapping

from sqlalchemy.orm import Session

from .core.enums import NotificationStatus
from .models import CommunicationDeliveryReport, CommunicationNotification, CommunicationWebhookEvent
from .core.state_machine import transition


def _record_security_event() -> None:
    try:
        from metrics import record_security_event
        record_security_event()
    except Exception:
        pass


def verify_signature(raw_body: bytes, signature: str | None, secret: str) -> None:
    if not secret:
        _record_security_event()
        raise ValueError("webhook secret is not configured")
    if not signature:
        _record_security_event()
        raise ValueError("webhook signature is required")
    provided = signature.removeprefix("sha256=").strip()
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(provided, expected):
        _record_security_event()
        raise ValueError("invalid webhook signature")


def _max_age_seconds() -> int:
    try:
        return max(0, int(os.getenv("PESAGUARD_WEBHOOK_MAX_AGE_SECONDS", "300")))
    except ValueError:
        return 300


def _validate_timestamp(payload: Mapping[str, Any], *, now: datetime | None = None) -> None:
    """Replay protection: reject callbacks older than the configured window.

    Africa's Talking callbacks that omit a timestamp are accepted (the HMAC
    still authenticates them); callbacks that carry one are enforced strictly.
    """
    raw = payload.get("timestamp") or payload.get("receivedAt") or payload.get("sentAt")
    if not raw:
        return
    now = now or datetime.now(timezone.utc)
    value = str(raw).strip()
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("webhook timestamp is invalid") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    skew_seconds = 60
    if parsed > now + timedelta_seconds(skew_seconds):
        raise ValueError("webhook timestamp is in the future")
    age = (now - parsed).total_seconds()
    max_age = _max_age_seconds()
    if max_age and age > max_age:
        raise ValueError("webhook timestamp is too old (possible replay)")


def timedelta_seconds(seconds: int):
    from datetime import timedelta

    return timedelta(seconds=seconds)


def _payload_hash(raw_body: bytes) -> str:
    return hashlib.sha256(raw_body).hexdigest()


def _parse_payload(raw_body: bytes) -> dict[str, Any]:
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("webhook payload must be valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("webhook payload must be an object")
    return payload


def process_delivery_webhook(
    session: Session,
    raw_body: bytes,
    *,
    signature: str | None,
    secret: str,
    provider: str = "africas_talking",
) -> dict[str, Any]:
    """Authenticated, idempotent, inbox-persisted delivery callback pipeline.

    Pipeline: signature -> schema -> replay protection -> idempotency ->
    persist inbox event -> apply status -> persist delivery report.
    Callbacks referencing unknown notifications are stored as `unprocessed`
    for administrative replay instead of failing the provider's retry loop.
    """
    verify_signature(raw_body, signature, secret)
    payload = _parse_payload(raw_body)
    _validate_timestamp(payload)

    provider_event_id = _required_string(payload, "id", "messageId", "messageID")
    event_type = _required_string(payload, "eventType", default="sms.delivery")
    existing = session.query(CommunicationWebhookEvent).filter_by(
        provider=provider,
        provider_event_id=provider_event_id,
        event_type=event_type,
    ).one_or_none()
    if existing is not None:
        return {"status": "duplicate", "event_id": existing.id}

    provider_message_id = _first_string(payload, "messageId", "messageID", "id")
    notification = session.query(CommunicationNotification).filter_by(
        provider=provider,
        provider_message_id=provider_message_id,
    ).one_or_none()

    now = datetime.now(timezone.utc)
    event = CommunicationWebhookEvent(
        id=f"communication_webhook_{uuid.uuid4().hex}",
        tenant_id=notification.tenant_id if notification is not None else None,
        provider=provider,
        provider_event_id=provider_event_id,
        event_type=event_type,
        payload=payload,
        payload_hash=_payload_hash(raw_body),
        status="received",
        processing_status="pending",
        signature_valid=1,
        attempt_count=1,
        received_at=now,
    )
    session.add(event)

    if notification is None:
        # Inbox pattern: persist for investigation/replay; respond OK so the
        # provider does not storm retries for a message we do not recognize.
        event.processing_status = "unprocessed"
        event.status = "unmatched"
        event.last_error = "delivery callback does not reference a known notification"
        session.flush()
        return {"status": "pending_review", "event_id": event.id}

    try:
        result = _apply_delivery_payload(session, notification, payload, provider, provider_event_id, now)
    except Exception as exc:
        event.processing_status = "unprocessed"
        event.last_error = str(exc)[:4000]
        session.flush()
        raise
    event.processing_status = "processed"
    event.status = "processed"
    event.processed_at = datetime.now(timezone.utc)
    session.flush()
    _publish_status_event(notification, provider, provider_event_id)
    return {"status": "processed", "event_id": event.id, "notification_id": notification.id, **result}


def replay_webhook_event(session: Session, event_id: str, *, provider: str = "africas_talking") -> dict[str, Any]:
    """Administratively reprocess a stored webhook event (audited by callers)."""
    event = session.query(CommunicationWebhookEvent).filter_by(id=event_id).one_or_none()
    if event is None:
        raise ValueError("webhook event not found")
    if event.processing_status == "processed":
        return {"status": "already_processed", "event_id": event.id}
    notification = session.query(CommunicationNotification).filter_by(
        provider=event.provider,
        provider_message_id=_first_string(event.payload or {}, "messageId", "messageID", "id"),
    ).one_or_none()
    event.attempt_count = (event.attempt_count or 0) + 1
    if notification is None:
        event.last_error = "replay failed: delivery callback does not reference a known notification"
        session.flush()
        return {"status": "unresolved", "event_id": event.id}
    now = datetime.now(timezone.utc)
    result = _apply_delivery_payload(session, notification, event.payload or {}, event.provider, event.provider_event_id, now)
    event.processing_status = "processed"
    event.status = "processed"
    event.processed_at = now
    event.last_error = None
    session.flush()
    _publish_status_event(notification, event.provider, event.provider_event_id)
    return {"status": "processed", "event_id": event.id, "notification_id": notification.id, **result}


def ignore_webhook_event(session: Session, event_id: str) -> dict[str, Any]:
    """Mark an inbox event as ignored so it no longer appears as actionable."""
    event = session.query(CommunicationWebhookEvent).filter_by(id=event_id).one_or_none()
    if event is None:
        raise ValueError("webhook event not found")
    event.processing_status = "ignored"
    event.processed_at = datetime.now(timezone.utc)
    session.flush()
    return {"status": "ignored", "event_id": event.id}


def _first_string(payload: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _required_string(payload: Mapping[str, Any], *keys: str, default: str | None = None) -> str:
    value = _first_string(payload, *keys)
    if value:
        return value
    if default is not None:
        return default
    raise ValueError(f"webhook field {keys[0]!r} is required")


def _map_delivery_status(value: Any) -> NotificationStatus:
    normalized = str(value or "").strip().casefold()
    if normalized in {"delivered", "delivery", "success"}:
        return NotificationStatus.DELIVERED
    if normalized in {"opened", "open"}:
        return NotificationStatus.OPENED
    if normalized in {"clicked", "click"}:
        return NotificationStatus.CLICKED
    if normalized in {"bounced", "bounce", "hard_bounce", "soft_bounce"}:
        return NotificationStatus.BOUNCED
    if normalized in {"complained", "complaint", "spam"}:
        return NotificationStatus.COMPLAINED
    if normalized in {"sent", "submitted"}:
        return NotificationStatus.SUBMITTED
    if normalized in {"expired", "failed", "rejected", "undelivered"}:
        return NotificationStatus.FAILED
    raise ValueError("unsupported delivery status")


def _apply_delivery_payload(
    session: Session,
    notification: CommunicationNotification,
    payload: Mapping[str, Any],
    provider: str,
    provider_event_id: str,
    now: datetime,
) -> dict[str, Any]:
    """Apply one delivery report to a notification (idempotent at DB level)."""
    status = _map_delivery_status(payload.get("status"))
    report = CommunicationDeliveryReport(
        id=f"delivery_{uuid.uuid4().hex}",
        notification_id=notification.id,
        tenant_id=notification.tenant_id,
        provider=provider,
        provider_event_id=provider_event_id,
        status=status.value,
        raw_payload=dict(payload),
        received_at=now,
        delivered_at=now if status == NotificationStatus.DELIVERED else None,
    )
    session.add(report)
    notification.status = transition(notification.status, status)
    notification.updated_at = now
    if status == NotificationStatus.SUBMITTED and notification.submitted_at is None:
        notification.submitted_at = now
    elif status == NotificationStatus.DELIVERED:
        if notification.delivered_at is None:
            notification.delivered_at = now
        if notification.submitted_at is None:
            notification.submitted_at = now
    elif status == NotificationStatus.FAILED and notification.failed_at is None:
        notification.failed_at = now
    return {"delivery_status": status.value}


def _publish_status_event(notification: CommunicationNotification, provider: str, provider_event_id: str) -> None:
    """Best-effort lifecycle event emission; never breaks webhook processing."""
    try:
        from .events import build_status_event, publish_status_event

        publish_status_event(build_status_event(
            notification.status,
            notification_id=notification.id,
            tenant_id=notification.tenant_id,
            provider=provider,
            provider_message_id=provider_event_id,
            correlation_id=notification.correlation_id,
            trace_id=notification.trace_id,
        ))
    except Exception:
        pass
