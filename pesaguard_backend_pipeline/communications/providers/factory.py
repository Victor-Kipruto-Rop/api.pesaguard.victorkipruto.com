from __future__ import annotations

from typing import Any

from ..core.enums import CommunicationChannel
from .africas_talking import AfricasTalkingProvider


def build_africas_talking_provider(client: Any | None = None) -> AfricasTalkingProvider:
    if client is None:
        from ..africas_talking import AfricasTalkingClient

        client = AfricasTalkingClient()
    return AfricasTalkingProvider(client)


def build_default_provider_for_channel(
    channel: CommunicationChannel,
    client: Any | None = None,
    **kwargs: Any,
):
    """Build the default provider adapter for a channel.

    SMS routes to Africa's Talking. Email uses the injected SMTP gateway.
    Voice/USSD/WhatsApp require a deployment-provided gateway client; without
    one the factory raises so callers never silently pretend to send.
    """
    if channel is CommunicationChannel.SMS:
        return build_africas_talking_provider(client)
    if channel is CommunicationChannel.EMAIL:
        from .smtp import SmtpEmailProvider

        from_email = kwargs.get("from_email") or kwargs.get("sender") or ""
        if client is None or not from_email:
            raise RuntimeError("email provider requires a gateway client and from_email")
        return SmtpEmailProvider(client, from_email=from_email)
    if client is None:
        raise RuntimeError(f"no default provider configured for channel {channel.value!r}; provide a gateway client")
    from .generic import GenericChannelProvider

    return GenericChannelProvider(f"gateway_{channel.value}", channel, client)
