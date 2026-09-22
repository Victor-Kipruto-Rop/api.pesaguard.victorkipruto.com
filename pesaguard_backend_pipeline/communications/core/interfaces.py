from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol

from .enums import CommunicationChannel, CommunicationPriority


@dataclass(frozen=True)
class NotificationRequest:
    tenant_id: str
    recipient: str
    message: str
    channel: CommunicationChannel = CommunicationChannel.SMS
    priority: CommunicationPriority = CommunicationPriority.NORMAL
    notification_id: str | None = None
    idempotency_key: str | None = None
    template_id: str | None = None
    variables: Mapping[str, Any] = field(default_factory=dict)
    correlation_id: str | None = None
    trace_id: str | None = None


@dataclass(frozen=True)
class ProviderMessage:
    provider: str
    provider_message_id: str | None
    status: str
    raw_response: Mapping[str, Any] = field(default_factory=dict)


class CommunicationProvider(Protocol):
    name: str
    supported_channels: frozenset[CommunicationChannel]

    def send(self, request: NotificationRequest) -> ProviderMessage:
        """Submit a communication and return provider acceptance state."""

    def validate_recipient(self, channel: CommunicationChannel, recipient: str) -> str:
        """Validate and normalize a recipient for a channel."""
