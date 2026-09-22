from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from deletion_workflow import DeletionWorkflow
import action_audit
from models import AuditEvent, Base, Transaction
from retention_policy import DataRetentionRule, RetentionPolicy


def policy(hot_days=90):
    return RetentionPolicy({"transactions": DataRetentionRule("Transaction data", "Finance", "retention", hot_days, "PostgreSQL", "finance", "anonymize")})


def _session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'deletion.db'}")
    Base.metadata.create_all(engine)
    action_audit.Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_retained_transaction_is_anonymized_and_audited(tmp_path):
    session = _session(tmp_path)
    transaction = Transaction(id="txn-1", trans_id="provider-1", tenant_id="tenant-a", trans_amount=10, msisdn="254700000000", business_short_code="123", trans_time="20260923120000", raw_payload={})
    session.add(transaction)
    session.commit()
    workflow = DeletionWorkflow(policy(90))
    request = workflow.request(session, tenant_id="tenant-a", transaction_id="txn-1", requested_by="admin", reason="user request")
    result = workflow.execute(session, request.id, authorize=lambda item: True, authorization_reference="approval-1")
    assert result.status == "anonymized"
    assert session.query(Transaction).one().msisdn.startswith("redacted:")
    assert session.query(AuditEvent).filter_by(event_type="data.deletion_completed").count() == 1


def test_expired_transaction_can_be_deleted_only_after_authorization(tmp_path):
    session = _session(tmp_path)
    session.add(Transaction(id="txn-old", trans_id="provider-old", tenant_id="tenant-a", trans_amount=10, msisdn="254700000000", business_short_code="123", trans_time="20240101120000", raw_payload={}, created_at=datetime.now(timezone.utc) - timedelta(days=100)))
    session.commit()
    workflow = DeletionWorkflow(policy(1))
    request = workflow.request(session, tenant_id="tenant-a", transaction_id="txn-old", requested_by="admin", reason="approved purge")
    result = workflow.execute(session, request.id, authorize=lambda item: True, authorization_reference="approval-2")
    assert result.status == "deleted"
    assert session.query(Transaction).count() == 0