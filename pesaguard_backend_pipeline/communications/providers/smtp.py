from __future__ import annotations

import re
from typing import Any

from ..core.enums import CommunicationChannel
from ..core.exceptions import PermanentCommunicationError, TransientCommunicationError
from ..core.interfaces import NotificationRequest, ProviderMessage
from .base import ProviderAdapter

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class SmtpEmailProvider(ProviderAdapter):
    """Email adapter over an injected SMTP gateway client.

    The gateway client exposes `send_message(message: dict) -> dict` with a
    `message_id` in the response, keeping transport details out of PesaGuard.
    """

    name = "smtp_email"
    supported_channels = frozenset({CommunicationChannel.EMAIL})

    def __init__(self, client: Any, *, from_email: str):
        self.client = client
        self.from_email = from_email

    def validate_recipient(self, channel: CommunicationChannel, recipient: str) -> str:
        normalized = super().validate_recipient(channel, recipient).strip().lower()
        if not _EMAIL_PATTERN.match(normalized):
            raise PermanentCommunicationError(
                "recipient is not a valid email address",
                code="INVALID_RECIPIENT",
            )
        return normalized

    def _send(self, request: NotificationRequest) -> ProviderMessage:
        recipient = self.validate_recipient(request.channel, request.recipient)
        subject = str((request.variables or {}).get("subject") or "PesaGuard notification")
        message = {
            "to": recipient,
            "from_email": self.from_email,
            "subject": subject,
            "body": request.message,
            "idempotency_key": request.idempotency_key,
        }
        try:
            response = self.client.send_message(message)
        except TimeoutError as exc:
            raise TransientCommunicationError("email gateway timed out", code="PROVIDER_TIMEOUT") from exc
        except ConnectionError as exc:
            raise TransientCommunicationError("email gateway connection failed", code="PROVIDER_REQUEST_ERROR") from exc
        except PermanentCommunicationError:
            raise
        except Exception as exc:
            raise TransientCommunicationError("email gateway request failed", code="PROVIDER_REQUEST_ERROR") from exc
        if not isinstance(response, dict) or not response.get("message_id"):
            raise PermanentCommunicationError("email gateway rejected message", code="PROVIDER_REJECTED")
        return ProviderMessage(
            provider=self.name,
            provider_message_id=str(response["message_id"]),
            status="accepted",
            raw_response=response,
        )