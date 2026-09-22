from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, text
from sqlalchemy.orm import Session

from .models import CommunicationNotification, CommunicationOutboxEntry
from .core.state_machine import transition


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def enqueue_notification(session: Session, notification: CommunicationNotification) -> CommunicationOutboxEntry:
    existing = session.query(CommunicationOutboxEntry).filter_by(notification_id=notification.id).one_or_none()
    if existing is not None:
        return existing
    entry = CommunicationOutboxEntry(
        id=f"comm_outbox_{uuid.uuid4().hex}",
        notification_id=notification.id,
        tenant_id=notification.tenant_id,
    )
    session.add(entry)
    notification.status = transition(notification.status, "queued")
    if notification.queued_at is None:
        notification.queued_at = utc_now()
    session.flush()
    return entry


_PRIORITY_ORDER = "CASE communication_notifications.priority "
_PRIORITY_ORDER += "WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'normal' THEN 2 WHEN 'low' THEN 3 WHEN 'bulk' THEN 4 ELSE 5 END"


def claim_entries(session: Session, *, worker_id: str, limit: int = 50, lease_seconds: int = 60) -> list[CommunicationOutboxEntry]:
    now = utc_now()
    query = (
        session.query(CommunicationOutboxEntry)
        .join(CommunicationNotification, CommunicationNotification.id == CommunicationOutboxEntry.notification_id)
        .filter(
            CommunicationOutboxEntry.status.in_(("pending", "retrying", "leased")),
            CommunicationOutboxEntry.available_at <= now,
            or_(CommunicationOutboxEntry.lease_expires_at.is_(None), CommunicationOutboxEntry.lease_expires_at <= now),
        )
        .order_by(
            text(_PRIORITY_ORDER),
            CommunicationOutboxEntry.available_at.asc(),
            CommunicationOutboxEntry.created_at.asc(),
        )
        .limit(limit)
    )
    try:
        query = query.with_for_update(skip_locked=True)
    except TypeError:
        query = query.with_for_update()
    entries = query.all()
    expiry = now + timedelta(seconds=lease_seconds)
    for entry in entries:
        entry.status = "leased"
        entry.leased_by = worker_id
        entry.lease_expires_at = expiry
        entry.attempt_count += 1
    session.flush()
    return entries


def complete_entry(session: Session, entry: CommunicationOutboxEntry, *, worker_id: str) -> None:
    _assert_lease(entry, worker_id)
    entry.status = "completed"
    entry.completed_at = utc_now()
    entry.lease_expires_at = None
    entry.leased_by = None
    notification = session.query(CommunicationNotification).filter_by(id=entry.notification_id).one()
    notification.updated_at = utc_now()


def fail_entry(
    session: Session,
    entry: CommunicationOutboxEntry,
    *,
    worker_id: str,
    error: str,
    retry_delay_seconds: int = 60,
    retryable: bool = True,
) -> None:
    _assert_lease(entry, worker_id)
    entry.last_error = error[:4000]
    entry.lease_expires_at = None
    entry.leased_by = None
    if not retryable:
        entry.status = "dead_letter"
        notification_status = "failed"
    elif entry.attempt_count >= entry.max_attempts:
        entry.status = "dead_letter"
        notification_status = "dead_letter"
    else:
        entry.status = "retrying"
        entry.available_at = utc_now() + timedelta(seconds=max(1, retry_delay_seconds))
        notification_status = "retrying"
    notification = session.query(CommunicationNotification).filter_by(id=entry.notification_id).one()
    notification.status = transition(notification.status, notification_status)
    notification.failure_reason = entry.last_error
    notification.updated_at = utc_now()


def replay_dead_letter(session: Session, entry_id: str) -> CommunicationOutboxEntry:
    entry = session.query(CommunicationOutboxEntry).filter_by(id=entry_id, status="dead_letter").one()
    entry.status = "pending"
    entry.attempt_count = 0
    entry.available_at = utc_now()
    entry.last_error = None
    notification = session.query(CommunicationNotification).filter_by(id=entry.notification_id).one()
    if notification.status == "dead_letter":
        notification.status = transition(notification.status, "queued")
        notification.queued_at = utc_now()
    elif notification.status == "failed":
        notification.status = transition(notification.status, "retrying")
    notification.failure_reason = None
    notification.updated_at = utc_now()
    session.flush()
    return entry


def _assert_lease(entry: CommunicationOutboxEntry, worker_id: str) -> None:
    expires = entry.lease_expires_at
    if expires is not None and expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if entry.status != "leased" or entry.leased_by != worker_id or expires is None or expires <= utc_now():
        raise RuntimeError("communication outbox lease is not owned by this worker")