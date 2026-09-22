from datetime import datetime, timedelta, timezone

import pytest

import app_2
from models import Base, Discrepancy
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def client(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)

    monkeypatch.setattr(app_2, "engine", engine)
    monkeypatch.setattr(app_2, "SessionLocal", SessionLocal)
    app_2.app.config["TESTING"] = True

    with app_2.app.test_client() as test_client:
        yield test_client


def seed_discrepancy(session, **overrides):
    detected_at = overrides.pop("detected_at", datetime.now(timezone.utc) - timedelta(minutes=15))
    discrepancy = Discrepancy(
        id=overrides.pop("id", "disc-1"),
        trans_id=overrides.pop("trans_id", "TX1"),
        tenant_id=overrides.pop("tenant_id", "tenant-a"),
        anomaly_type=overrides.pop("anomaly_type", "missing_payment"),
        status=overrides.pop("status", "needs_review"),
        severity=overrides.pop("severity", "critical"),
        details=overrides.pop("details", "Missing payment"),
        resolved=overrides.pop("resolved", False),
        detected_at=detected_at,
        assignee=overrides.pop("assignee", None),
        notes=overrides.pop("notes", "Initial note"),
        timeline=overrides.pop("timeline", [{"ts": detected_at.isoformat(), "event": "created", "message": "Created"}]),
    )
    session.add(discrepancy)
    session.commit()
    return discrepancy


def test_discrepancies_include_sla_metadata(client):
    with app_2.SessionLocal() as session:
        seed_discrepancy(session, id="disc-sla", severity="critical")

    response = client.get("/discrepancies")
    assert response.status_code == 200
    data = response.get_json()
    assert data["items"][0]["sla_status"] in {"breaching", "warning", "on_track"}
    assert "sla_remaining_minutes" in data["items"][0]


def test_activity_feed_and_assignment_queue_are_available(client):
    with app_2.SessionLocal() as session:
        seed_discrepancy(session, id="disc-feed", severity="warning")

    activity = client.get("/activity-feed?limit=5")
    assert activity.status_code == 200
    assert activity.get_json()["items"][0]["event"] == "created"

    queue = client.get("/assignment-queue")
    assert queue.status_code == 200
    assert queue.get_json()["items"][0]["queue_status"] in {"needs_assignment", "assigned"}
