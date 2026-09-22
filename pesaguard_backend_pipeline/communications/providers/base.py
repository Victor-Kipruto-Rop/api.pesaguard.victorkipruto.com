from __future__ import annotations

from collections.abc import Mapping

from ..core.enums import CommunicationChannel
from ..core.exceptions import PermanentCommunicationError
from ..core.interfaces import CommunicationProvider, NotificationRequest, ProviderMessage


class UnsupportedChannelError(PermanentCommunicationError):
    def __init__(self, channel: CommunicationChannel, provider: str):
        super().__init__(
            f"Provider {provider!r} does not support channel {channel.value!r}",
            code="CHANNEL_UNSUPPORTED",
        )


class ProviderAdapter:
    """Small base adapter that centralizes channel capability checks."""

    name = "provider"
    supported_channels: frozenset[CommunicationChannel] = frozenset()

    def send(self, request: NotificationRequest) -> ProviderMessage:
        if request.channel not in self.supported_channels:
            raise UnsupportedChannelError(request.channel, self.name)
        return self._send(request)

    def _send(self, request: NotificationRequest) -> ProviderMessage:
        raise NotImplementedError

    def validate_recipient(self, channel: CommunicationChannel, recipient: str) -> str:
        if channel not in self.supported_channels:
            raise UnsupportedChannelError(channel, self.name)
        if not isinstance(recipient, str) or not recipient.strip():
            raise ValueError("recipient must be a non-empty string")
        return recipient.strip()
