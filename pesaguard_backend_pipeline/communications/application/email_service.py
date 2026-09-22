from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from ..core.enums import CommunicationChannel, NotificationStatus
from ..core.exceptions import CommunicationError
from ..core.interfaces import CommunicationProvider, NotificationRequest
from ..models import CommunicationNotification
from .notification_service import NotificationService
from ..providers.email import (
    EmailProviderAnalytics,
    EmailProviderConfig,
    EmailProviderFactory,
    EmailProviderHealth,
    EmailProviderRegistry,
    EmailRouter,
)


class EmailService:
    """Enterprise-facing email service facade built on the repo's provider contracts.

    It keeps the business-facing email object name in one place while delegating
    transport binding to the existing provider registry and factory model.
    """

    def __init__(
        self,
        session: Session | None,
        gateway_client: Any | None = None,
        config: EmailProviderConfig | None = None,
        registry: EmailProviderRegistry | None = None,
        provider: CommunicationProvider | None = None,
        analytics: EmailProviderAnalytics | None = None,
    ):
        self.session = session
        self.config = config or EmailProviderConfig()
        self.registry = registry or EmailProviderRegistry()
        self.gateway_client = gateway_client
        self.analytics = analytics or EmailProviderAnalytics()
        self.factory = EmailProviderFactory(
            gateway_client=gateway_client,
            config=self.config,
            registry=self.registry,
        )
        self.provider = provider or self.factory.create()
        self.router = EmailRouter(
            {self.provider.name: self.provider},
            order={CommunicationChannel.EMAIL: [self.provider.name]},
        )
        self.health = EmailProviderHealth()

    def send(self, request: NotificationRequest, *, cost: dict[str, Any] | None = None, latency_ms: int | None = None) -> CommunicationNotification:
        """Submit a notification through the repository's existing send pipeline.

        If a SQLAlchemy session is present, it persists and tracks the
        notification using the standard NotificationService. Otherwise, this
        service constructs an in-memory notification object so tests and local
        developer flows can still exercise the email facade without a DB.

        The optional cost and latency carry-through keeps the compatibility
        analytics object and the CommunicationAttempt model aligned with the
        enterprise email metadata the repository already stores.
        """
        if self.session is not None:
            notification = NotificationService(self.session, self.provider).send(
                request,
                cost=cost,
                latency_ms=latency_ms,
            )
            return notification

        # Local/off-DB execution path for deterministic repository resilience work.
        if not request.idempotency_key:
            raise ValueError("idempotency_key is required for notification delivery")

        if request.channel != CommunicationChannel.EMAIL:
            raise ValueError("EmailService only supports email notifications")

        started = None
        try:
            started = __import__("time").monotonic()
            provider_message = self.provider.send(request)
        except CommunicationError as exc:
            actual_latency_ms = int((__import__("time").monotonic() - started) * 1000) if started is not None else latency_ms or 0
            self.health.register_result(self.provider.name, failed=True, latency_ms=actual_latency_ms)
            self.analytics.record_failure(self.provider.name, str(exc), latency_ms=actual_latency_ms, cost=cost, notification_id=request.notification_id)
            raise
        except Exception as exc:
            actual_latency_ms = int((__import__("time").monotonic() - started) * 1000) if started is not None else latency_ms or 0
            self.health.register_result(self.provider.name, failed=True, latency_ms=actual_latency_ms)
            self.analytics.record_failure(self.provider.name, "PROVIDER_REQUEST_ERROR", latency_ms=actual_latency_ms, cost=cost, notification_id=request.notification_id)
            raise CommunicationError(str(exc), code="PROVIDER_REQUEST_ERROR", retryable=True) from exc

        actual_latency_ms = int((__import__("time").monotonic() - started) * 1000) if started is not None else latency_ms or 0
        self.health.register_result(self.provider.name, failed=False, latency_ms=actual_latency_ms)
        self.analytics.record_success(self.provider.name, latency_ms=actual_latency_ms, cost=cost, notification_id=request.notification_id)
        notification = CommunicationNotification(
            id=request.notification_id or f"notification_{uuid.uuid4().hex}",
            tenant_id=request.tenant_id,
            channel=request.channel.value,
            recipient=self.provider.validate_recipient(request.channel, request.recipient),
            message=request.message,
            template_id=request.template_id,
            priority=request.priority.value,
            status=NotificationStatus.ACCEPTED.value,
            idempotency_key=request.idempotency_key,
            provider=self.provider.name,
            correlation_id=request.correlation_id,
            trace_id=request.trace_id,
            metadata_json={**dict(request.variables or {}), "email_cost": cost, "email_latency_ms": actual_latency_ms},
        )
        notification.provider_message_id = provider_message.provider_message_id
        notification.status = NotificationStatus.ACCEPTED.value
        return notification

    def enqueue(self, request: NotificationRequest, *, cost: dict[str, Any] | None = None, latency_ms: int | None = None) -> CommunicationNotification:
        """Persist the notification into outbox semantics by reusing the repo's standard service."""
        if self.session is None:
            return self.send(request, cost=cost, latency_ms=latency_ms)
        return NotificationService(self.session, self.provider).enqueue(request, cost=cost, latency_ms=latency_ms)

    def health_snapshot(self) -> dict[str, Any]:
        base = self.health.snapshot()
        base["analytics"] = self.analytics.snapshot(self.session)
        return base
