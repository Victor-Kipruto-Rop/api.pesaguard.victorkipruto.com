import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, "pesaguard_backend_pipeline")

from escalation_engine import EscalationEngine
from models import Base, Discrepancy


def build_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    return Session()


def test_webhook_action_triggers_http_post(monkeypatch):
    session = build_session()
    incident = Discrepancy(
        id="inc-1",
        trans_id="txn-1",
        tenant_id="tenant-a",
        anomaly_type="double_charge",
        severity="critical",
        details="Possible duplicate transfer",
        status="needs_review",
    )
    session.add(incident)
    session.commit()

    engine = EscalationEngine(session)
    engine.create_rule(
        tenant_id="tenant-a",
        name="Critical webhook",
        description="Notify external system",
        condition_field="severity",
        condition_operator="equals",
        condition_value="critical",
        action="webhook",
        webhook_url="https://example.test/hook",
        priority=10,
    )

    calls = []

    class DummyResponse:
        status_code = 200
        text = "ok"

    def fake_post(url, json=None, headers=None, timeout=None):
        calls.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        return DummyResponse()

    monkeypatch.setattr("escalation_engine.requests.post", fake_post)

    result = engine.evaluate_and_escalate("tenant-a", incident)

    assert result["details"][0]["status"] == "webhook_triggered"
    assert calls[0]["url"] == "https://example.test/hook"


def test_notify_action_sends_email(monkeypatch, tmp_path):
    session = build_session()
    incident = Discrepancy(
        id="inc-2",
        trans_id="txn-2",
        tenant_id="tenant-a",
        anomaly_type="suspicious_amount",
        severity="high",
        details="Large transfer above threshold",
        status="needs_review",
    )
    session.add(incident)
    session.commit()

    settings_path = tmp_path / "tenant_settings.json"
    settings_path.write_text(
        '{"default": {"preferred_locale": "en"}, "tenant-a": {"preferred_locale": "sw"}}',
        encoding="utf-8",
    )
    monkeypatch.setenv("TENANT_SETTINGS_FILE", str(settings_path))

    engine = EscalationEngine(session)
    engine.create_rule(
        tenant_id="tenant-a",
        name="High severity email",
        description="Email on-call operator",
        condition_field="severity",
        condition_operator="equals",
        condition_value="high",
        action="notify",
        target="ops@example.com",
        priority=5,
    )

    calls = []

    class DummyEmailService:
        def __init__(self, *args, **kwargs):
            pass

        def send_escalation_notification(self, session_obj, tenant_id, recipient_email, incident_data, locale=None):
            calls.append({
                "tenant_id": tenant_id,
                "recipient_email": recipient_email,
                "incident_data": incident_data,
                "locale": locale,
            })
            return {"status": "sent"}

    monkeypatch.setattr("escalation_engine.EmailService", DummyEmailService)

    result = engine.evaluate_and_escalate("tenant-a", incident)

    assert result["details"][0]["status"] == "notification_sent"
    assert calls[0]["recipient_email"] == "ops@example.com"
    assert calls[0]["locale"] == "sw"
