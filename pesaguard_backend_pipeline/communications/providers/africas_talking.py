from __future__ import annotations

from typing import Any

from ..core.enums import CommunicationChannel
from ..core.exceptions import PermanentCommunicationError, TransientCommunicationError
from ..core.interfaces import NotificationRequest, ProviderMessage
from .base import ProviderAdapter


class AfricasTalkingProvider(ProviderAdapter):
    """Africa's Talking adapter behind the provider-neutral contract."""

    name = "africas_talking"
    supported_channels = frozenset({CommunicationChannel.SMS})

    def __init__(self, client: Any):
        self.client = client

    def validate_recipient(self, channel: CommunicationChannel, recipient: str) -> str:
        normalized = super().validate_recipient(channel, recipient)
        try:
            return self.client._normalize_phone_number(normalized)
        except Exception as exc:
            raise PermanentCommunicationError(
                "recipient is not a valid Kenyan mobile number",
                code="INVALID_RECIPIENT",
            ) from exc

    def _send(self, request: NotificationRequest) -> ProviderMessage:
        recipient = self.validate_recipient(request.channel, request.recipient)
        result = self.client.send_sms(
            recipient,
            request.message,
            idempotency_key=request.idempotency_key,
        )
        status = str(result.get("status", "failed"))
        if status == "sent":
            response = result.get("response")
            return ProviderMessage(
                provider=self.name,
                provider_message_id=_provider_message_id(response),
                status="accepted",
                raw_response=result,
            )
        if status == "skipped":
            raise PermanentCommunicationError("Africa's Talking is not configured", code="PROVIDER_NOT_CONFIGURED")
        if result.get("reason") in {"timeout_ambiguous", "request_error"}:
            raise TransientCommunicationError(
                "Africa's Talking request did not complete",
                code="PROVIDER_TIMEOUT" if result.get("reason") == "timeout_ambiguous" else "PROVIDER_REQUEST_ERROR",
            )
        raise PermanentCommunicationError(
            str(result.get("error_code") or result.get("reason") or "provider rejected message"),
            code="PROVIDER_REJECTED",
        )


def _provider_message_id(response: Any) -> str | None:
    if not isinstance(response, dict):
        return None
    message_data = response.get("SMSMessageData")
    if not isinstance(message_data, dict):
        return None
    recipients = message_data.get("Recipients")
    if not isinstance(recipients, list) or not recipients or not isinstance(recipients[0], dict):
        return None
    value = recipients[0].get("messageId") or recipients[0].get("messageID")
    return str(value) if value else None
