import importlib
import os
import tempfile

from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import pesaguard_backend_pipeline.retention_cleanup as retention_cleanup_mod
from pesaguard_backend_pipeline.models import Base, Discrepancy, ReconciliationOutbox, Transaction, TransactionOutbox
from pesaguard_backend_pipeline.action_audit import ActionAuditEntry, AuditLegalHold


def test_cleanup_retention_deletes_older_records(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "retention_test.db")
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
        monkeypatch.setenv("PESAGUARD_RETENTION_DAYS_TRANSACTIONS", "1")
        monkeypatch.setenv("PESAGUARD_RETENTION_DAYS_DISCREPANCIES", "1")
        monkeypatch.setenv("PESAGUARD_RETENTION_DAYS_AUDIT", "1")

        engine = create_engine(f"sqlite:///{db_path}")
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine, expire_on_commit=False)

        session = Session()
        try:
            old_time = datetime.now(timezone.utc) - timedelta(days=2)
            recent_time = datetime.now(timezone.utc)
            session.add_all([
                Transaction(trans_id="old-tx", tenant_id="tenant-a", trans_amount=10.0, msisdn="254700000000", business_short_code="123", trans_time="20240101120000", raw_payload={}, created_at=old_time),
                Transaction(trans_id="old-delete", tenant_id="tenant-a", trans_amount=11.0, msisdn="254700000002", business_short_code="123", trans_time="20240101120000", raw_payload={}, created_at=old_time),
                Transaction(trans_id="new-tx", tenant_id="tenant-a", trans_amount=20.0, msisdn="254700000001", business_short_code="123", trans_time="20240101120000", raw_payload={}, created_at=recent_time),
                Discrepancy(id="old-disc", trans_id="old-tx", tenant_id="tenant-a", anomaly_type="missing_payment", status="needs_review", severity="critical", details="old", detected_at=old_time),
                Discrepancy(id="new-disc", trans_id="new-tx", tenant_id="tenant-a", anomaly_type="duplicate", status="needs_review", severity="warning", details="new", detected_at=recent_time),
                ActionAuditEntry(id="old-audit", tenant_id="tenant-a", actor="system", action="cleanup", details={}, created_at=old_time),
                ActionAuditEntry(id="new-audit", tenant_id="tenant-a", actor="system", action="cleanup", details={}, created_at=recent_time),
                TransactionOutbox(id="old-published", tenant_id="tenant-a", event_key="old-published", topic="t", payload={}, status="published", created_at=old_time, available_at=old_time),
                TransactionOutbox(id="old-failed", tenant_id="tenant-a", event_key="old-failed", topic="t", payload={}, status="failed", created_at=old_time, available_at=old_time),
                ReconciliationOutbox(id="old-recon", tenant_id="tenant-a", event_key="old-recon", topic="t", payload={}, status="published", created_at=old_time, available_at=old_time),
                AuditLegalHold(id="hold-old-tx", tenant_id="tenant-a", scope_type="transaction", scope_id="old-tx", reason="investigation", placed_by="test"),
            ])
            session.commit()
        finally:
            session.close()

        retention_cleanup = importlib.reload(retention_cleanup_mod)
        result = retention_cleanup.cleanup_retention()
        assert result["deleted_transactions"] == 1
        assert result["deleted_discrepancies"] == 0
        assert result["deleted_transaction_outbox"] == 1
        assert result["deleted_reconciliation_outbox"] == 1
        assert result["deleted_audit"] == 0
        assert result["eligible_audit_entries"] == 1
        assert result["post_delete_counts"]["transaction_outbox"] == 0
        engine.dispose()
