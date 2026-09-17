from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import Base, ReconciliationGroundTruth, ReconciliationMatch
from operations.ground_truth_certification import register_cases, validate_cases


def test_register_and_validate_approved_business_cases(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'ground-truth.db'}")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        cases = [
            {"transaction_id": "case-1", "expected_status": "MATCHED", "name": "approved exact"},
            {"transaction_id": "case-2", "expected_status": "UNMATCHED", "name": "approved missing"},
        ]
        assert register_cases(session, cases, "tenant-a", "finance-approver", "approval-2026-001") == 2
        assert session.query(ReconciliationGroundTruth).count() == 2
        assert session.query(ReconciliationGroundTruth).filter_by(approved_by="finance-approver").count() == 2

        session.add(ReconciliationMatch(
            id="match-1",
            tenant_id="tenant-a",
            transaction_id="case-1",
            matched_record={"internal_ref": "case-1"},
            matching_rules=["reference_exact"],
            match_score=1,
            match_timestamp=datetime.now(timezone.utc),
            engine_version="phase3.1",
            status="MATCHED",
            processing_latency_ms=1,
        ))
        session.commit()
        result = validate_cases(session, "tenant-a", "reconciliation-reviewer")
        assert result["validated_cases"] == 1
        assert result["missing_matches"] == ["case-2"]
        assert result["certified"] is False
    finally:
        session.close()
