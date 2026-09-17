import json
from pathlib import Path

from pesaguard_backend_pipeline import backup_postgres


def test_backup_status_marker_is_machine_readable(tmp_path: Path, monkeypatch):
    status_file = tmp_path / "last_status.json"
    monkeypatch.setattr(backup_postgres, "STATUS_FILE", status_file)
    backup_postgres._write_status("succeeded", artifact="pesaguard.sql.gz", offsite_configured=True)
    payload = json.loads(status_file.read_text(encoding="utf-8"))
    assert payload["status"] == "succeeded"
    assert payload["artifact"] == "pesaguard.sql.gz"
    assert payload["offsite_configured"] is True
    assert payload["updated_at"]


def test_restore_validation_checks_structural_and_business_gates(monkeypatch):
    from pesaguard_backend_pipeline.operations import validate_restore

    responses = {
        "SELECT count(*) FROM transactions": "10",
        "SELECT count(*) FROM processed_transactions": "10",
        "SELECT count(*) FROM transaction_outbox": "2",
        "SELECT count(*) FROM action_audit_entries": "10",
        "SELECT count(*) FROM fraud_risk_assessments": "10",
        "SELECT count(*) FROM reconciliation_matches": "8",
        "SELECT count(*) FROM pg_constraint WHERE conrelid = 'transactions'::regclass": "6",
        "SELECT count(*) FROM pg_indexes WHERE tablename IN ('transactions', 'processed_transactions', 'transaction_outbox')": "9",
        "SELECT count(*) FROM processed_transactions pt LEFT JOIN transactions t ON pt.transaction_id = t.id WHERE t.id IS NULL": "0",
        "SELECT count(*) FROM discrepancies d WHERE NOT EXISTS (SELECT 1 FROM action_audit_entries a WHERE a.details::text LIKE '%' || d.id::text || '%')": "0",
        "SELECT COALESCE(SUM(trans_amount), 0) FROM transactions": "150.00",
        "SELECT COALESCE(SUM(amount), 0) FROM reconciliation_matches WHERE amount IS NOT NULL": "150.00",
    }
    monkeypatch.setattr(validate_restore, "_query", lambda _url, sql: responses[sql])
    result = validate_restore.validate("postgresql://test")
    assert result["status"] == "passed"
    assert result["counts"]["transactions"] == 10
    assert result["audit_rows"] == 10
    assert result["reconciliation_rows"] == 8


def test_restore_validation_detects_integrity_violation(monkeypatch):
    """Exit gate: a validation failure must be surfaced when constraints/indexes are missing."""
    from pesaguard_backend_pipeline.operations import validate_restore

    responses = {
        "SELECT count(*) FROM transactions": "10",
        "SELECT count(*) FROM processed_transactions": "10",
        "SELECT count(*) FROM transaction_outbox": "2",
        "SELECT count(*) FROM action_audit_entries": "10",
        "SELECT count(*) FROM fraud_risk_assessments": "10",
        "SELECT count(*) FROM reconciliation_matches": "8",
        "SELECT count(*) FROM pg_constraint WHERE conrelid = 'transactions'::regclass": "0",
        "SELECT count(*) FROM pg_indexes WHERE tablename IN ('transactions', 'processed_transactions', 'transaction_outbox')": "0",
        "SELECT count(*) FROM processed_transactions pt LEFT JOIN transactions t ON pt.transaction_id = t.id WHERE t.id IS NULL": "0",
        "SELECT count(*) FROM discrepancies d WHERE NOT EXISTS (SELECT 1 FROM action_audit_entries a WHERE a.details::text LIKE '%' || d.id::text || '%')": "0",
        "SELECT COALESCE(SUM(trans_amount), 0) FROM transactions": "150.00",
        "SELECT COALESCE(SUM(amount), 0) FROM reconciliation_matches WHERE amount IS NOT NULL": "150.00",
    }
    monkeypatch.setattr(validate_restore, "_query", lambda _url, sql: responses[sql])
    result = validate_restore.validate("postgresql://test")
    assert result["status"] == "failed"
    assert result["constraints"] == 0
    assert result["indexes"] == 0
