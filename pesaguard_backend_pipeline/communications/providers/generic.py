from __future__ import annotations

from typing import Any

from ..core.enums import CommunicationChannel
from ..core.exceptions import PermanentCommunicationError, TransientCommunicationError
from ..core.interfaces import NotificationRequest, ProviderMessage
from .base import ProviderAdapter


class GenericChannelProvider(ProviderAdapter):
    """Adapter for channel gateways whose HTTP client is injected by deployment."""

    def __init__(self, name: str, channel: CommunicationChannel, client: Any):
        self.name = name
        self.supported_channels = frozenset({channel})
        self.channel = channel
        self.client = client

    def _send(self, request: NotificationRequest) -> ProviderMessage:
        try:
            response = self.client.send(channel=self.channel.value, recipient=request.recipient, message=request.message, idempotency_key=request.idempotency_key)
        except TimeoutError as exc:
            raise TransientCommunicationError("channel provider timed out", code="PROVIDER_TIMEOUT") from exc
        except Exception as exc:
            raise TransientCommunicationError("channel provider request failed", code="PROVIDER_REQUEST_ERROR") from exc
        if not isinstance(response, dict) or response.get("status") not in {"accepted", "sent", "submitted"}:
            raise PermanentCommunicationError("channel provider rejected message", code="PROVIDER_REJECTED")
        return ProviderMessage(self.name, str(response.get("id")) if response.get("id") else None, "accepted", response)