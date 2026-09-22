from pesaguard_backend_pipeline.communications.core.enums import CommunicationChannel
from pesaguard_backend_pipeline.communications.core.interfaces import NotificationRequest
from pesaguard_backend_pipeline.communications.application.email_service import EmailService
from pesaguard_backend_pipeline.communications.providers.email import (
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
from pesaguard_backend_pipeline.communications.providers.factory import build_default_provider_for_channel
from pesaguard_backend_pipeline.communications.providers.generic import GenericChannelProvider
from pesaguard_backend_pipeline.communications.providers.smtp import SmtpEmailProvider
from pesaguard_backend_pipeline.communications.product_routes import _csv_cell


class Gateway:
    def send(self, **kwargs):
        return {"status": "accepted", "id": f"{kwargs['channel']}-1"}


def test_all_non_sms_channel_adapters_use_the_same_contract():
    request_base = {"tenant_id": "tenant-a", "recipient": "recipient", "message": "hello", "idempotency_key": "id-1"}
    for channel in (CommunicationChannel.EMAIL, CommunicationChannel.VOICE, CommunicationChannel.USSD, CommunicationChannel.WHATSAPP):
        provider = GenericChannelProvider(f"gateway-{channel.value}", channel, Gateway())
        result = provider.send(NotificationRequest(channel=channel, **request_base))
        assert result.status == "accepted"
        assert result.provider_message_id == f"{channel.value}-1"


def test_load_style_batch_can_route_many_messages_without_cross_tenant_state():
    provider = GenericChannelProvider("gateway", CommunicationChannel.WHATSAPP, Gateway())
    results = [provider.send(NotificationRequest(tenant_id=f"tenant-{index % 3}", recipient=f"user-{index}", message="hello", channel=CommunicationChannel.WHATSAPP, idempotency_key=f"id-{index}")) for index in range(100)]
    assert len(results) == 100
    assert {result.provider for result in results} == {"gateway"}


def test_email_provider_and_factory_use_the_same_contract():
    class EmailGateway:
        def send_message(self, message):
            return {"message_id": "smtp-42"}

    provider = SmtpEmailProvider(EmailGateway(), from_email="noreply@pesaguard.example")
    result = provider.send(NotificationRequest(
        tenant_id="tenant-a",
        recipient="ops@example.com",
        message="hello",
        channel=CommunicationChannel.EMAIL,
        idempotency_key="email-1",
        variables={"subject": "Daily report"},
    ))
    assert result.provider == "smtp_email"
    assert result.provider_message_id == "smtp-42"
    assert result.status == "accepted"

    factory_provider = build_default_provider_for_channel(CommunicationChannel.EMAIL, client=EmailGateway(), from_email="noreply@pesaguard.example")
    assert factory_provider.name == "smtp_email"


def test_email_provider_abstraction_layer_is_exposed_and_compatible():
    class EmailGateway:
        def send_message(self, message):
            return {"message_id": "smtp-99"}

    config = EmailProviderConfig(provider="smtp_email", from_email="noreply@pesaguard.example")
    factory = EmailProviderFactory(gateway_client=EmailGateway(), config=config)
    provider = factory.create()
    assert isinstance(provider, SmtpEmailProvider)

    request = NotificationRequest(
        tenant_id="tenant-a",
        recipient="ops@example.com",
        message="hello",
        channel=CommunicationChannel.EMAIL,
        idempotency_key="email-2",
        variables={"subject": "Daily report"},
    )
    health = EmailProviderHealth()
    router = EmailRouter({provider.name: provider}, order={CommunicationChannel.EMAIL: [provider.name]})
    result = router.send(request)
    assert result.provider == "smtp_email"
    assert result.provider_message_id == "smtp-99"
    assert health.score >= 0


def test_email_provider_factory_supports_mock_provider_and_provider_registry_forms():
    class Gate:
        def send_message(self, message):
            return {"message_id": "mock-sent-1"}

    config = EmailProviderConfig(provider="mock_email", from_email="noreply@pesaguard.example")
    factory = EmailProviderFactory(gateway_client=Gate(), config=config)
    provider = factory.create()
    assert provider.name == "mock_email"

    result = provider.send(NotificationRequest(
        tenant_id="tenant-a",
        recipient="ops@example.com",
        message="hello",
        channel=CommunicationChannel.EMAIL,
        idempotency_key="email-3",
        variables={"subject": "Daily report"},
    ))
    assert result.provider == "mock_email"
    assert result.provider_message_id == "mock-sent-1"


def test_email_provider_registry_supports_aliases_and_provider_case_insensitivity():
    class EmailGateway:
        def send_message(self, message):
            return {"message_id": "smtp-100"}

    registry = EmailProviderRegistry()
    assert registry.get("SMTP") is SmtpEmailProvider
    assert registry.get("MOCK") is MockEmailProvider

    config = EmailProviderConfig(provider="smtp", from_email="noreply@pesaguard.example")
    factory = EmailProviderFactory(gateway_client=EmailGateway(), config=config, registry=registry)
    provider = factory.create()
    assert provider.name == "smtp_email"


def test_email_provider_registry_supports_real_provider_adapters_and_email_service_analytics_handoff():
    class EmailGateway:
        def send_message(self, message):
            return {"message_id": "sendgrid-201"}

    registry = EmailProviderRegistry()
    assert registry.get("ses") is SesEmailProvider
    assert registry.get("sendgrid") is SendGridEmailProvider
    assert registry.get("mailgun") is MailgunEmailProvider

    analytics = EmailProviderAnalytics()
    service = EmailService(
        None,
        gateway_client=EmailGateway(),
        config=EmailProviderConfig(provider="sendgrid", from_email="noreply@pesaguard.example"),
        registry=registry,
        analytics=analytics,
    )
    request = NotificationRequest(
        tenant_id="tenant-a",
        recipient="ops@example.com",
        message="hello",
        channel=CommunicationChannel.EMAIL,
        idempotency_key="email-analytics-1",
        variables={"subject": "Daily report"},
    )
    notification = service.send(request)
    assert notification.provider == "sendgrid_email"
    assert notification.provider_message_id == "sendgrid-201"
    assert analytics.snapshot()["providers"]["sendgrid_email"]["successes"] >= 1


def test_export_sanitizes_formula_cells():
    assert _csv_cell("=HYPERLINK('https://evil.example')").startswith("'=")
    assert _csv_cell("normal") == "normal"