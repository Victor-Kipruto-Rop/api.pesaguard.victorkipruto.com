from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from pesaguard_backend_pipeline.communications.core.enums import CommunicationChannel
from pesaguard_backend_pipeline.communications.domain import approve_template, create_template, is_allowed_now, issue_otp, render_template, set_consent, verify_otp
from pesaguard_backend_pipeline.communications.models import CommunicationPreference
from pesaguard_backend_pipeline.communications.providers.router import ProviderRouter
from pesaguard_backend_pipeline.models import Base
from pesaguard_backend_pipeline.communications.core.exceptions import TransientCommunicationError
from pesaguard_backend_pipeline.communications.core.interfaces import ProviderMessage


class Provider:
    def __init__(self, name, failures=0):
        self.name = name
        self.supported_channels = frozenset({CommunicationChannel.SMS})
        self.failures = failures

    def send(self, request):
        if self.failures:
            self.failures -= 1
            raise TransientCommunicationError("temporary outage")
        return ProviderMessage(self.name, f"{self.name}-1", "accepted")

    def validate_recipient(self, channel, recipient):
        return recipient


def session():
    engine = create_engine("sqlite://")
    import pesaguard_backend_pipeline.communications.models  # noqa: F401
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_template_approval_rendering_and_consent_are_tenant_scoped():
    db = session()
    template = create_template(db, tenant_id="tenant-a", slug="payment", channel=CommunicationChannel.SMS, body="Paid {amount} {currency}", variables=["amount", "currency"])
    assert render_template(template, {"amount": 12, "currency": "KES"}) == "Paid 12 KES"
    approve_template(db, template, "operator-1")
    consent = set_consent(db, tenant_id="tenant-a", recipient="+254700000001", channel=CommunicationChannel.SMS, purpose="transactional", granted=True)
    db.commit()
    assert template.status == "approved"
    assert consent.granted == 1


def test_quiet_hours_and_otp_attempt_limits():
    db = session()
    preference = CommunicationPreference(id="p1", tenant_id="tenant-a", recipient="+254700000001", quiet_hours_start="22:00", quiet_hours_end="06:00", timezone="UTC")
    assert not is_allowed_now(preference, now=datetime(2026, 9, 8, 23, 0, tzinfo=timezone.utc))
    assert is_allowed_now(preference, now=datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc))
    challenge, code = issue_otp(db, tenant_id="tenant-a", recipient="+254700000001", purpose="login")
    assert verify_otp(db, challenge, "000000") is False
    assert verify_otp(db, challenge, code) is True
    assert verify_otp(db, challenge, code) is False


def test_provider_router_fails_over_after_transient_error():
    primary, backup = Provider("primary", failures=3), Provider("backup")
    router = ProviderRouter({"primary": primary, "backup": backup}, {CommunicationChannel.SMS: ["primary", "backup"]}, failure_threshold=3)
    from pesaguard_backend_pipeline.communications.core.interfaces import NotificationRequest
    request = NotificationRequest(tenant_id="tenant-a", recipient="+254700000001", message="hello", idempotency_key="k")
    result = router.send(request)
    assert result.provider == "backup"