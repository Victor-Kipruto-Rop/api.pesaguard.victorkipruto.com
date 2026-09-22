import os
import sys
from types import SimpleNamespace

import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from shared.daraja.auth_client import DarajaAuthClient


class DummyResponse:
    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json_data = json_data or {}
        self.text = text

    def json(self):
        return self._json_data


def test_token_is_cached(monkeypatch):
    class DummySession:
        def __init__(self):
            self.calls = 0

        def get(self, url, auth=None, timeout=None):
            self.calls += 1
            return DummyResponse(status_code=200, json_data={"access_token": "token-1", "expires_in": 3600})

    session = DummySession()
    client = DarajaAuthClient(
        tenant_id="tenant-a",
        credentials={"consumer_key": "k", "consumer_secret": "s", "base_url": "https://sandbox.safaricom.co.ke"},
        session=session,
    )

    first = client.get_access_token()
    second = client.get_access_token()

    assert first == "token-1"
    assert second == "token-1"
    assert session.calls == 1


def test_401_triggers_refresh(monkeypatch):
    class DummySession:
        def __init__(self):
            self.oauth_calls = 0
            self.request_calls = 0

        def get(self, url, auth=None, timeout=None):
            self.oauth_calls += 1
            token = "token-1" if self.oauth_calls == 1 else "token-2"
            return DummyResponse(status_code=200, json_data={"access_token": token, "expires_in": 3600})

        def request(self, method, url, headers=None, **kwargs):
            self.request_calls += 1
            if self.request_calls == 1:
                return DummyResponse(status_code=401, json_data={"error": "expired"})
            return DummyResponse(status_code=200, json_data={"ok": True})

    session = DummySession()
    client = DarajaAuthClient(
        tenant_id="tenant-b",
        credentials={"consumer_key": "k", "consumer_secret": "s", "base_url": "https://sandbox.safaricom.co.ke"},
        session=session,
    )

    response = client.request("POST", "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest", json={"Amount": 10})

    assert response.status_code == 200
    assert session.oauth_calls >= 2
    assert session.request_calls == 2
