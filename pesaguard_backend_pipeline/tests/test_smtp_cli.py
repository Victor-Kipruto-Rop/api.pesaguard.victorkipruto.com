"""Offline regression tests for the explicitly invoked live SMTP utility."""
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def cli():
    path = Path(__file__).with_name("test_smtp.py")
    spec = importlib.util.spec_from_file_location("smtp_cli_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_import_has_no_side_effects(monkeypatch):
    import smtplib
    import dotenv
    blocked = MagicMock(side_effect=AssertionError("Unexpected side effect"))
    monkeypatch.setattr(smtplib, "SMTP", blocked)
    monkeypatch.setattr(smtplib, "SMTP_SSL", blocked)
    monkeypatch.setattr(dotenv, "load_dotenv", blocked)
    path = Path(__file__).with_name("test_smtp.py")
    spec = importlib.util.spec_from_file_location("smtp_import_check", path)
    spec.loader.exec_module(importlib.util.module_from_spec(spec))
    blocked.assert_not_called()


@pytest.mark.parametrize("args", [[], ["--send"], ["--send", "--to", "a@example.test,b@example.test"], ["--send", "--check-only"]])
def test_explicit_action_and_single_recipient_required(cli, monkeypatch, args):
    factory = MagicMock()
    monkeypatch.setattr(cli, "create_service", factory)
    with pytest.raises(SystemExit) as error:
        cli.main(args)
    assert error.value.code == 2
    factory.assert_not_called()


def test_check_only_never_sends(cli, monkeypatch):
    service = MagicMock()
    service.configuration_error.return_value = None
    monkeypatch.setattr(cli, "create_service", lambda: service)
    assert cli.main(["--check-only"]) == 0
    service._send_email.assert_not_called()
    service._executor.shutdown.assert_called_once_with(wait=True)


@pytest.mark.parametrize("success,code", [(True, 0), (False, 1)])
def test_send_uses_requested_recipient_once(cli, monkeypatch, success, code):
    service = MagicMock()
    service.configuration_error.return_value = None
    service._send_email.return_value = (success, None)
    monkeypatch.setattr(cli, "create_service", lambda: service)
    assert cli.main(["--send", "--to", "recipient@example.test"]) == code
    service._send_email.assert_called_once()
    assert service._send_email.call_args.args[0] == "recipient@example.test"


def test_configuration_failure_never_connects(cli, monkeypatch, capsys):
    service = MagicMock()
    service.configuration_error.return_value = "SMTP delivery requires TLS"
    monkeypatch.setattr(cli, "create_service", lambda: service)
    assert cli.main(["--check-only"]) == 1
    service._send_email.assert_not_called()
    assert "requires TLS" in capsys.readouterr().out


def test_exception_is_redacted(cli, monkeypatch, capsys):
    monkeypatch.setattr(cli, "create_service", MagicMock(side_effect=ValueError("private-value")))
    assert cli.main(["--check-only"]) == 1
    assert "private-value" not in capsys.readouterr().out
