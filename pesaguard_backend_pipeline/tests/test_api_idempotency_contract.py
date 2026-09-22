import importlib

import pytest

from models import Base, IdempotencyRecord, Transaction


@pytest.fixture()
def api_client(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'api-idempotency.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("PESAGUARD_API_AUTH_REQUIRED", "0")
    monkeypatch.setenv("JWT_SECRET_KEY", "phase1-test-secret-012345678901234567890123")
    import app as webhook_app

    webhook_app = importlib.reload(webhook_app)
    webhook_app.app.config.update(TESTING=True)
    webhook_app.event_store._ensure_ready()
    Base.metadata.create_all(webhook_app.event_store.engine)
    with webhook_app.app.test_client() as client:
        yield client, webhook_app.event_store


def _request(client, key, transaction_id="api-contract-1"):
    return client.post(
        "/api/v1/transactions",
        headers={"Idempotency-Key": key, "X-Tenant-ID": "tenant-api"},
        json={
            "provider_transaction_id": transaction_id,
            "provider_account_id": "600000",
            "provider": "mpesa",
            "TransAmount": "25.00",
            "Currency": "KES",
            "MSISDN": "254700000000",
            "TransTime": "20260913120000",
        },
    )


def test_api_idempotency_key_replays_without_duplication(api_client):
    client, store = api_client
    first = _request(client, "api-key-1")
    second = _request(client, "api-key-1")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json["duplicate"] is False
    assert second.json["duplicate"] is True
    with store.Session() as session:
        assert session.query(Transaction).count() == 1
        assert session.query(IdempotencyRecord).count() == 1


def test_api_idempotency_requires_key_and_tenant(api_client):
    client, _ = api_client
    assert client.post("/api/v1/transactions", json={}).status_code == 400
    assert client.post(
        "/api/v1/transactions",
        headers={"Idempotency-Key": "missing-tenant"},
        json={},
    ).status_code == 400