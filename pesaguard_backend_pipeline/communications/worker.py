from __future__ import annotations

import json
import logging
import os
import socket
import uuid
import random
from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy.orm import Session

import time
from .core.enums import CommunicationChannel, CommunicationPriority
from .core.error_categories import ProviderErrorCategory, category_for_exception, is_retryable
from .core.interfaces import NotificationRequest
from .core.state_machine import transition
from .core.exceptions import CommunicationError
from .cost import build_cost
from .incidents import report_incident, sla_breach
from .models import CommunicationAttempt, CommunicationNotification
from .outbox import claim_entries, complete_entry, fail_entry
from .providers.factory import build_africas_talking_provider

logger = logging.getLogger(__name__)

_PROVIDER_FAILURE_THRESHOLD = max(1, int(os.getenv("PESAGUARD_COMMUNICATION_PROVIDER_INCIDENT_THRESHOLD", "10")))
_MAX_ATTEMPTS_DEFAULT = 5


def process_outbox_once(
    session: Session,
    *,
    provider_factory: Callable[[], Any] = build_africas_talking_provider,
    worker_id: str | None = None,
    limit: int = 50,
    publish_events: bool = True,
) -> int:
    worker_id = worker_id or f"{socket.gethostname()}-{uuid.uuid4().hex[:8]}"
    entries = claim_entries(session, worker_id=worker_id, limit=limit)
    provider_failures: dict[str, int] = {}
    for entry in entries:
        notification = session.query(CommunicationNotification).filter_by(id=entry.notification_id).one()
        notification.status = transition(notification.status, "processing")
        _report_sla_breach_if_needed(session, notification)
        started_at = datetime.now(timezone.utc)
        attempt = CommunicationAttempt(
            id=f"attempt_{uuid.uuid4().hex}",
            notification_id=notification.id,
            attempt_number=entry.attempt_count,
            provider=notification.provider or "unknown",
            status="processing",
            started_at=started_at,
            cost=build_cost(CommunicationChannel(notification.channel), notification.message),
        )
        session.add(attempt)
        try:
            provider = provider_factory()
            request = NotificationRequest(
                tenant_id=notification.tenant_id,
                recipient=notification.recipient,
                message=notification.message,
                channel=CommunicationChannel(notification.channel),
                priority=CommunicationPriority(notification.priority),
                idempotency_key=notification.idempotency_key,
                notification_id=notification.id,
                template_id=notification.template_id,
                variables=notification.metadata_json or {},
                correlation_id=notification.correlation_id,
                trace_id=notification.trace_id,
            )
            result = provider.send(request)
            latency_ms = int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000)
            notification.provider = result.provider
            notification.provider_message_id = result.provider_message_id
            notification.status = transition(notification.status, result.status)
            if notification.submitted_at is None and notification.status in {"accepted", "submitted", "sent"}:
                notification.submitted_at = datetime.now(timezone.utc)
            attempt.status = result.status
            attempt.provider = result.provider
            attempt.provider_message_id = result.provider_message_id
            attempt.latency_ms = latency_ms
            attempt.completed_at = datetime.now(timezone.utc)
            complete_entry(session, entry, worker_id=worker_id)
            if publish_events:
                _publish_transition(notification, result.provider, result.provider_message_id)
        except CommunicationError as exc:
            _handle_send_failure(session, notification=notification, entry=entry, attempt=attempt, exc=exc,
                                 worker_id=worker_id, started_at=started_at, publish_events=publish_events,
                                 provider_failures=provider_failures)
        except Exception as exc:
            wrapped = CommunicationError(str(exc), code="PROVIDER_UNAVAILABLE", retryable=True)
            _handle_send_failure(session, notification=notification, entry=entry, attempt=attempt, exc=wrapped,
                                 worker_id=worker_id, started_at=started_at, publish_events=publish_events,
                                 provider_failures=provider_failures)
        session.commit()
    return len(entries)


def _handle_send_failure(
    session: Session,
    *,
    notification: CommunicationNotification,
    entry,
    attempt: CommunicationAttempt,
    exc: CommunicationError,
    worker_id: str,
    started_at: datetime,
    publish_events: bool,
    provider_failures: dict[str, int],
) -> None:
    category = category_for_exception(exc)
    latency_ms = int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000)
    max_attempts = entry.max_attempts or _MAX_ATTEMPTS_DEFAULT
    will_retry = bool(exc.retryable and is_retryable(category) and entry.attempt_count < max_attempts)
    attempt.status = "retrying" if will_retry else "dead_letter"
    attempt.error_code = exc.code
    attempt.error_category = category.value
    attempt.error_detail = str(exc)
    attempt.latency_ms = latency_ms
    attempt.completed_at = datetime.now(timezone.utc)
    provider_name = attempt.provider or "unknown"
    provider_failures[provider_name] = provider_failures.get(provider_name, 0) + 1
    failure_count = provider_failures[provider_name]
    fail_entry(
        session,
        entry,
        worker_id=worker_id,
        error=f"[{category.value}] {exc}",
        retry_delay_seconds=_retry_delay(entry.attempt_count),
        retryable=will_retry,
    )
    if notification.failed_at is None and not will_retry:
        notification.failed_at = datetime.now(timezone.utc)
    if publish_events:
        _publish_transition(notification, provider_name, notification.provider_message_id)
    if failure_count >= _PROVIDER_FAILURE_THRESHOLD:
        provider_failures[provider_name] = 0
        try:
            report_incident(
                session,
                category="provider",
                title=f"Repeated {category.value} failures from {provider_name}",
                fingerprint=f"provider_degradation_{provider_name}",
                severity="high",
                tenant_id=notification.tenant_id,
                metrics={"error_category": category.value, "provider": provider_name, "consecutive_failures": failure_count},
                summary=f"Worker {worker_id} observed repeated consecutive failures; circuit breaker and failover policy are active.",
            )
        except Exception:
            logger.exception("failed to record provider degradation incident")


def _report_sla_breach_if_needed(session: Session, notification: CommunicationNotification) -> None:
    try:
        created_at = notification.created_at
        if created_at is None:
            return
        breach = sla_breach(created_at, notification.priority or "normal")
        if breach is None:
            return
        report_incident(
            session,
            category="sla",
            title=f"Notification SLA breach ({notification.priority} priority)",
            fingerprint=f"sla_breach_{notification.tenant_id}_{notification.priority}",
            severity="high" if notification.priority in {"critical", "high"} else "medium",
            tenant_id=notification.tenant_id,
            metrics=breach,
            summary=f"Queue latency {breach['actual_seconds']}s exceeded the {breach['target_seconds']}s target for {notification.priority} notifications.",
            affected_count=1,
        )
    except Exception:
        logger.exception("failed to evaluate notification SLA breach")


def _publish_transition(notification: CommunicationNotification, provider: str, provider_message_id: str | None) -> None:
    try:
        from .events import build_status_event, publish_status_event

        publish_status_event(build_status_event(
            notification.status,
            notification_id=notification.id,
            tenant_id=notification.tenant_id,
            provider=provider,
            provider_message_id=provider_message_id,
            correlation_id=notification.correlation_id,
            trace_id=notification.trace_id,
        ))
    except Exception:
        logger.debug("status event publication skipped", exc_info=True)


def consume_notification_events(session_factory: Callable[[], Session], *, provider_factory: Callable[[], Any] = build_africas_talking_provider) -> None:
    """Consume notification Kafka events when kafka-python-ng is installed."""
    from kafka import KafkaConsumer

    consumer = KafkaConsumer(
        os.getenv("PESAGUARD_NOTIFICATION_TOPIC", "notification.events"),
        bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
        group_id=os.getenv("PESAGUARD_NOTIFICATION_GROUP", "pesaguard-communications"),
        enable_auto_commit=False,
        value_deserializer=lambda value: json.loads(value.decode("utf-8")),
    )
    for message in consumer:
        session = session_factory()
        try:
            event = message.value
            if event.get("recipient"):
                from .application.notification_service import NotificationService
                NotificationService(session, provider_factory()).enqueue(NotificationRequest(
                    tenant_id=event["tenant_id"],
                    recipient=event["recipient"],
                    message=str(event.get("context", {}).get("message", event["event"])),
                    idempotency_key=str(event.get("event_id") or f"{message.topic}:{message.partition}:{message.offset}"),
                    correlation_id=event.get("correlation_id"),
                    trace_id=event.get("trace_id"),
                ))
            session.commit()
            consumer.commit()
        except Exception:
            session.rollback()
            logger.exception("Notification event processing failed")
        finally:
            session.close()


def run_worker(session_factory: Callable[[], Session], *, provider_factory: Callable[[], Any] = build_africas_talking_provider) -> None:
    """Run the durable outbox loop; Kafka ingestion is enabled separately by configuration."""
    from .governor import RateGovernor, default_provider_rate_per_minute

    worker_id = f"{socket.gethostname()}-{uuid.uuid4().hex[:8]}"
    interval = max(1, int(os.getenv("PESAGUARD_OUTBOX_POLL_SECONDS", "5")))
    governor = RateGovernor(provider_rates={"africas_talking": default_provider_rate_per_minute()})
    while True:
        session = session_factory()
        try:
            processed = process_outbox_once(session, provider_factory=provider_factory, worker_id=worker_id)
            if processed:
                wait = governor.wait_seconds("africas_talking")
                if wait > 0:
                    time.sleep(min(wait, interval))
        finally:
            session.close()
        time.sleep(interval)


def _session_factory() -> Session:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(os.getenv("DATABASE_URL", "postgresql://pesaguard:pesaguard@localhost:5432/pesaguard"), pool_pre_ping=True)
    try:
        from metrics import instrument_engine_query_timing
        instrument_engine_query_timing(engine)
    except Exception:
        logger.debug("Communications worker engine query timing instrumentation skipped.", exc_info=True)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def _retry_delay(attempt: int) -> int:
    base = max(1, int(os.getenv("PESAGUARD_COMMUNICATION_RETRY_BASE_SECONDS", "5")))
    maximum = max(base, int(os.getenv("PESAGUARD_COMMUNICATION_RETRY_MAX_SECONDS", "600")))
    jitter_ratio = min(1.0, max(0.0, float(os.getenv("PESAGUARD_COMMUNICATION_RETRY_JITTER", "0.25"))))
    delay = min(maximum, base * (2 ** max(0, attempt - 1)))
    return max(1, int(delay + random.uniform(0, delay * jitter_ratio)))


if __name__ == "__main__":
    run_worker(lambda: _session_factory())
