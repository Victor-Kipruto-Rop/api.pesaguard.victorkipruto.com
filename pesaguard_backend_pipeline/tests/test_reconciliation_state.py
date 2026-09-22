from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from action_audit import ActionAuditEntry
from event_store import EventStore, ProcessResult
from models import Base, Discrepancy, ProcessedTransaction, ReconciliationOutbox
from reconciliation_job import _persist_atomically


def _event():
    return {
        "TransID": "TX-STATE-1",
        "TransAmount": "10.00",
        "MSISDN": "254700000000",
        "BusinessShortCode": "123456",
        "TransTime": "20260912120000",
    }


def test_reconciliation_is_separate_from_ingestion_and_replay_safe(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'reconciliation.db'}"
    engine = create_engine(database_url)

    import reconciliation_job
    from action_audit import Base as AuditBase

    Base.metadata.create_all(engine)
    AuditBase.metadata.create_all(engine)
    monkeypatch.setattr(reconciliation_job, "AuditSession", sessionmaker(bind=engine, expire_on_commit=False))
    store = EventStore(database_url=database_url)
    event = _event()
    assert store.mark_processed(event, tenant_id="tenant-a") is ProcessResult.STORED

    evaluation = {
        "status": "missing_payment",
        "severity": "critical",
        "match": {"match_type": "none"},
        "anomalies": ["missing_payment"],
        "event": event,
        "tenant_id": "tenant-a",
    }
    assert _persist_atomically(event, evaluation, event["TransID"], "tenant-a") is ProcessResult.STORED
    assert _persist_atomically(event, evaluation, event["TransID"], "tenant-a") is ProcessResult.DUPLICATE

    with sessionmaker(bind=engine)() as session:
        assert session.query(ProcessedTransaction).one().reconciliation_status == "completed"
        assert session.query(Discrepancy).count() == 1
        assert session.query(ActionAuditEntry).count() == 1
        assert session.query(ReconciliationOutbox).count() == 1
