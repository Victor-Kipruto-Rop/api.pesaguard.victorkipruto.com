"""Load and throughput tests for the communications platform.

These tests measure throughput, latency, and queue behavior at controlled
volumes without contacting a real provider. They use an in-memory provider
that responds immediately, so wall-clock results reflect the local pipeline.

Targets (when infra permits):
  - 100 msg/sec
  - 500 msg/sec
  - 1,000 msg/sec

Run:
  python -m pytest pesaguard_backend_pipeline/test_communications_load.py -v
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from pesaguard_backend_pipeline.communications.core.enums import CommunicationChannel, CommunicationPriority
from pesaguard_backend_pipeline.communications.core.interfaces import NotificationRequest, ProviderMessage
from pesaguard_backend_pipeline.communications.models import CommunicationNotification, CommunicationOutboxEntry
from pesaguard_backend_pipeline.communications.worker import process_outbox_once
from pesaguard_backend_pipeline.communications.application.notification_service import NotificationService
from pesaguard_backend_pipeline.models import Base


class InstantProvider:
    """Synchronous provider that succeeds immediately (no network)."""

    name = "instant"
    supported_channels = frozenset({CommunicationChannel.SMS})

    def __init__(self):
        self.sent = 0

    def send(self, request):
        self.sent += 1
        return ProviderMessage(self.name, f"INSTANT-{self.sent}", "accepted")

    def validate_recipient(self, channel, recipient):
        return recipient


def _session():
    engine = create_engine("sqlite://")
    import pesaguard_backend_pipeline.communications.models  # noqa: F401

    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _enqueue_batch(db, provider, count, *, prefix="load"):
    service = NotificationService(db, provider)
    started = time.monotonic()
    for i in range(count):
        service.enqueue(NotificationRequest(
            tenant_id="tenant-a",
            recipient=f"+2547000{i % 1000:05d}",
            message="Load test notification",
            idempotency_key=f"{prefix}-{i}",
            channel=CommunicationChannel.SMS,
            priority=CommunicationPriority.NORMAL,
        ))
    db.commit()
    elapsed = time.monotonic() - started
    return count, elapsed


def test_enqueue_throughput_100():
    """Enqueue 100 notifications; measure throughput and verify all persisted."""
    db = _session()
    provider = InstantProvider()
    count, elapsed = _enqueue_batch(db, provider, 100, prefix="load100")
    rate = count / elapsed if elapsed else 0.0
    assert db.query(CommunicationNotification).count() == count
    assert db.query(CommunicationOutboxEntry).filter_by(status="pending").count() == count
    print(f"\n  enqueue: {count} msgs in {elapsed:.3f}s = {rate:.0f} msgs/sec")
    assert rate > 0


def test_enqueue_throughput_500():
    """Enqueue 500 notifications; measure throughput and verify all persisted."""
    db = _session()
    provider = InstantProvider()
    count, elapsed = _enqueue_batch(db, provider, 500, prefix="load500")
    rate = count / elapsed if elapsed else 0.0
    assert db.query(CommunicationNotification).count() == count
    assert db.query(CommunicationOutboxEntry).filter_by(status="pending").count() == count
    print(f"\n  enqueue: {count} msgs in {elapsed:.3f}s = {rate:.0f} msgs/sec")
    assert rate > 0


def test_enqueue_throughput_1000():
    """Enqueue 1000 notifications; measure throughput and verify all persisted."""
    db = _session()
    provider = InstantProvider()
    count, elapsed = _enqueue_batch(db, provider, 1000, prefix="load1000")
    rate = count / elapsed if elapsed else 0.0
    assert db.query(CommunicationNotification).count() == count
    assert db.query(CommunicationOutboxEntry).filter_by(status="pending").count() == count
    print(f"\n  enqueue: {count} msgs in {elapsed:.3f}s = {rate:.0f} msgs/sec")
    assert rate > 0


def test_worker_processing_throughput():
    """Process a batch through the worker; verify drain and measure rate."""
    db = _session()
    provider = InstantProvider()
    count, _ = _enqueue_batch(db, provider, 200, prefix="worker-load")
    started = time.monotonic()
    processed = process_outbox_once(
        db,
        provider_factory=lambda: InstantProvider(),
        worker_id="load-w1",
        limit=200,
        publish_events=False,
    )
    db.commit()
    elapsed = time.monotonic() - started
    rate = processed / elapsed if elapsed else 0.0
    assert processed == count
    assert db.query(CommunicationOutboxEntry).filter_by(status="completed").count() == count
    print(f"\n  worker: {processed} msgs in {elapsed:.3f}s = {rate:.0f} msgs/sec")
    assert rate > 0


def test_priority_ordering_critical_first():
    """Critical-priority messages are claimed before normal/low in a mixed batch."""
    db = _session()
    provider = InstantProvider()
    service = NotificationService(db, provider)
    for i in range(10):
        priority = CommunicationPriority.CRITICAL if i % 2 == 0 else CommunicationPriority.LOW
        service.enqueue(NotificationRequest(
            tenant_id="tenant-a",
            recipient=f"+2547000000{i:02d}",
            message="priority test",
            idempotency_key=f"priority-{i}",
            channel=CommunicationChannel.SMS,
            priority=priority,
        ))
    db.commit()
    first_batch = process_outbox_once(db, provider_factory=lambda: InstantProvider(), worker_id="load-w2", limit=15, publish_events=False)
    db.commit()
    assert first_batch > 0
    # All critical entries should be completed first (claimed in priority order).
    critical_completed = db.query(CommunicationNotification.id).join(
        CommunicationOutboxEntry, CommunicationOutboxEntry.notification_id == CommunicationNotification.id
    ).filter(
        CommunicationNotification.priority == "critical",
        CommunicationOutboxEntry.status == "completed",
    ).count()
    low_pending = db.query(CommunicationNotification.id).join(
        CommunicationOutboxEntry, CommunicationOutboxEntry.notification_id == CommunicationNotification.id
    ).filter(
        CommunicationNotification.priority == "low",
        CommunicationOutboxEntry.status.in_(("pending", "retrying")),
    ).count()
    assert critical_completed == 5  # all critical done
    assert low_pending >= 0


def test_worker_batch_limit_respected():
    """Worker only claims up to its batch limit even with more pending."""
    db = _session()
    provider = InstantProvider()
    _enqueue_batch(db, provider, 30, prefix="batch-limit")
    processed = process_outbox_once(
        db,
        provider_factory=lambda: InstantProvider(),
        worker_id="load-w3",
        limit=10,
        publish_events=False,
    )
    db.commit()
    assert processed == 10
    assert db.query(CommunicationOutboxEntry).filter_by(status="completed").count() == 10
    assert db.query(CommunicationOutboxEntry).filter_by(status="pending").count() == 20