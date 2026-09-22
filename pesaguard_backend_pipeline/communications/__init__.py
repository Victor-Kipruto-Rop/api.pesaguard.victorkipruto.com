"""Provider-neutral communications platform for PesaGuard."""

from .application.email_service import EmailService
from .core.enums import CommunicationChannel, CommunicationPriority, NotificationStatus
from .core.exceptions import CommunicationError, PermanentCommunicationError, TransientCommunicationError
from .core.interfaces import CommunicationProvider, NotificationRequest, ProviderMessage
from .events import (
    fraud_notification_event,
    reconciliation_notification_event,
    security_notification_event,
    transaction_notification_event,
)
from .providers.email import (
    EmailProviderAnalytics,
    EmailProviderConfig,
    EmailProviderFactory,
    EmailProviderHealth,
    EmailProviderRegistry,
    EmailRouter,
    MailgunEmailProvider,
    MockEmailProvider,
    SendGridEmailProvider,
    SesEmailProvider,
)

__all__ = [
    "CommunicationChannel",
    "CommunicationPriority",
    "CommunicationProvider",
    "CommunicationError",
    "NotificationRequest",
    "NotificationStatus",
    "PermanentCommunicationError",
    "ProviderMessage",
    "TransientCommunicationError",
    "EmailService",
    "EmailProviderAnalytics",
    "EmailProviderConfig",
    "EmailProviderFactory",
    "EmailProviderHealth",
    "EmailProviderRegistry",
    "EmailRouter",
    "MailgunEmailProvider",
    "MockEmailProvider",
    "SendGridEmailProvider",
    "SesEmailProvider",
    "fraud_notification_event",
    "reconciliation_notification_event",
    "security_notification_event",
    "transaction_notification_event",
]
