"""SMTP transport tests: deployment credentials and network are never used."""
import ssl
from unittest.mock import MagicMock

import pytest

import email_service as email_module


@pytest.fixture
def smtp_setup(monkeypatch):
    for name in (
        "EMAIL_HOST", "EMAIL_PORT", "EMAIL_USERNAME", "EMAIL_PASSWORD", "EMAIL_FROM",
        "EMAIL_USE_TLS", "EMAIL_USE_SSL", "SMTP_SERVER", "SMTP_PORT", "SMTP_FROM_EMAIL",
        "SMTP_HOST", "SMTP_USERNAME", "SMTP_PASSWORD", "SMTP_USE_TLS", "SMTP_USE_SSL", "SMTP_FROM_NAME",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")
    monkeypatch.setenv("EMAIL_HOST", "smtp.example.test")
    monkeypatch.setenv("EMAIL_FROM", "sender@example.test")
    smtp = MagicMock()
    smtp.return_value.send_message.return_value = {}
    secure = MagicMock()
    secure.return_value.send_message.return_value = {}
    monkeypatch.setattr(email_module.smtplib, "SMTP", smtp)
    monkeypatch.setattr(email_module.smtplib, "SMTP_SSL", secure)
    services = []

    def create(**kwargs):
        service = email_module.EmailService(**kwargs)
        services.append(service)
        return service

    yield create, smtp, secure
    for service in services:
        service._executor.shutdown(wait=True)


def send(service):
    return service._send_email("recipient@example.test", "Test", "<p>Test</p>", "Test")


def assert_verified(context):
    assert context.check_hostname is True
    assert context.verify_mode == ssl.CERT_REQUIRED


def test_starttls_environment_and_authentication(monkeypatch, smtp_setup):
    create, smtp, secure = smtp_setup
    monkeypatch.setenv("EMAIL_USERNAME", "test-user")
    monkeypatch.setenv("EMAIL_PASSWORD", "isolated-test-password")
    service = create()
    assert send(service) == (True, None)
    smtp.assert_called_once_with("smtp.example.test", 587, timeout=10)
    server = smtp.return_value
    assert_verified(server.starttls.call_args.kwargs["context"])
    server.login.assert_called_once_with("test-user", "isolated-test-password")
    names = [entry[0] for entry in server.mock_calls]
    assert names.index("starttls") < names.index("login") < names.index("send_message")
    message = server.send_message.call_args.args[0]
    assert message["From"] == "PesaGuard <sender@example.test>"
    assert message["To"] == "recipient@example.test"
    assert len(message.get_payload()) == 2
    secure.assert_not_called()


def test_implicit_tls(monkeypatch, smtp_setup):
    create, smtp, secure = smtp_setup
    monkeypatch.setenv("EMAIL_USE_SSL", "true")
    assert send(create()) == (True, None)
    assert secure.call_args.args == ("smtp.example.test", 465)
    assert_verified(secure.call_args.kwargs["context"])
    secure.return_value.starttls.assert_not_called()
    smtp.assert_not_called()


def test_constructor_overrides_and_legacy_names(monkeypatch, smtp_setup):
    create, _, _ = smtp_setup
    monkeypatch.delenv("EMAIL_HOST")
    monkeypatch.delenv("EMAIL_FROM")
    monkeypatch.setenv("SMTP_SERVER", "legacy.example.test")
    monkeypatch.setenv("SMTP_PORT", "2525")
    monkeypatch.setenv("SMTP_FROM_EMAIL", "legacy@example.test")
    legacy = create()
    assert (legacy.smtp_server, legacy.smtp_port, legacy.from_email) == (
        "legacy.example.test", 2525, "legacy@example.test",
    )
    explicit = create(smtp_server="explicit.example.test", smtp_port=587, from_email="explicit@example.test")
    assert explicit.smtp_server == "explicit.example.test"
    monkeypatch.setenv("EMAIL_HOST", "")
    assert create().smtp_server == ""


@pytest.mark.parametrize("settings", [
    {"EMAIL_HOST": ""}, {"EMAIL_FROM": ""},
    {"EMAIL_USERNAME": "test-user"}, {"EMAIL_PASSWORD": "test-only"},
    {"EMAIL_USE_TLS": "false", "EMAIL_USE_SSL": "false"},
])
def test_invalid_delivery_configuration_does_not_connect(monkeypatch, smtp_setup, settings):
    create, smtp, secure = smtp_setup
    for key, value in settings.items():
        monkeypatch.setenv(key, value)
    assert send(create())[0] is False
    smtp.assert_not_called()
    secure.assert_not_called()


@pytest.mark.parametrize("settings", [
    {"EMAIL_PORT": "invalid"}, {"EMAIL_PORT": "0"}, {"EMAIL_PORT": "65536"},
    {"EMAIL_USE_TLS": "maybe"}, {"EMAIL_USE_TLS": "true", "EMAIL_USE_SSL": "true"},
])
def test_invalid_constructor_configuration(monkeypatch, smtp_setup, settings):
    create, _, _ = smtp_setup
    for key, value in settings.items():
        monkeypatch.setenv(key, value)
    with pytest.raises(ValueError):
        create()


def test_tls_failure_does_not_login_or_expose_response(smtp_setup, caplog):
    create, smtp, _ = smtp_setup
    smtp.return_value.starttls.side_effect = RuntimeError("sensitive-provider-response")
    assert send(create()) == (False, "SMTP delivery failed")
    smtp.return_value.login.assert_not_called()
    smtp.return_value.send_message.assert_not_called()
    assert "sensitive-provider-response" not in caplog.text


def test_refused_recipient_is_not_success(smtp_setup):
    create, smtp, _ = smtp_setup
    smtp.return_value.send_message.return_value = {"recipient@example.test": (550, b"refused")}
    assert send(create()) == (False, "SMTP recipients refused")


@pytest.mark.parametrize("implicit", [False, True])
def test_smtp_names_take_precedence(monkeypatch, smtp_setup, implicit):
    create, smtp, secure = smtp_setup
    values = {
        "SMTP_HOST": "preferred.example.test", "SMTP_PORT": "465" if implicit else "587",
        "SMTP_USERNAME": "preferred-user", "SMTP_PASSWORD": "test-only-password",
        "SMTP_FROM_EMAIL": "preferred@example.test", "SMTP_FROM_NAME": "Test Sender",
        "SMTP_USE_TLS": str(not implicit), "SMTP_USE_SSL": str(implicit),
        "EMAIL_USERNAME": "legacy-user", "EMAIL_PASSWORD": "legacy-test-only",
        "EMAIL_USE_TLS": str(implicit), "EMAIL_USE_SSL": str(not implicit),
        "EMAIL_PORT": "2525",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    service = create()
    assert send(service) == (True, None)
    transport = secure if implicit else smtp
    assert transport.call_args.args == ("preferred.example.test", 465 if implicit else 587)
    transport.return_value.login.assert_called_once_with("preferred-user", "test-only-password")
    assert transport.return_value.send_message.call_args.args[0]["From"] == "Test Sender <preferred@example.test>"
    explicit = create(smtp_server="override.example.test", from_name="Override", username="override", password="override-test")
    assert explicit.smtp_server == "override.example.test"
    assert explicit.from_name == "Override"
    assert explicit.username == "override"


@pytest.mark.parametrize("name", ["SMTP_HOST", "SMTP_FROM_EMAIL", "SMTP_USERNAME"])
def test_empty_preferred_value_does_not_fall_back(monkeypatch, smtp_setup, name):
    create, smtp, secure = smtp_setup
    monkeypatch.setenv("EMAIL_USERNAME", "legacy-user")
    monkeypatch.setenv("EMAIL_PASSWORD", "test-only")
    monkeypatch.setenv(name, "")
    assert send(create())[0] is False
    smtp.assert_not_called()
    secure.assert_not_called()


def test_connection_failure_diagnostics_are_safe(smtp_setup, caplog):
    create, smtp, _ = smtp_setup
    smtp.side_effect = TimeoutError("private-provider-detail")
    assert send(create()) == (False, "SMTP delivery failed")
    assert "phase=connection" in caplog.text
    assert "error_type=TimeoutError" in caplog.text
    assert "private-provider-detail" not in caplog.text

