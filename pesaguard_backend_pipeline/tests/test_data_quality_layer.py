from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from data_quality import DataQualityStatus, dq_report, run_data_quality
from models import Base, QuarantineRecord
from provenance import DataProvenance


def _payload(**overrides):
    payload = {
        "TransID": "dq-1",
        "TenantID": "tenant-a",
        "Provider": "mpesa",
        "TransAmount": "100.00",
        "Currency": "KES",
        "BillRefNumber": "member-1",
        "schema_version": "1.0",
    }
    payload.update(overrides)
    return payload


def test_data_quality_report_scores_all_dimensions():
    result = run_data_quality(_payload())

    assert result.status == DataQualityStatus.PASS
    assert result.dimension_scores == {
        "completeness": 1.0,
        "uniqueness": 1.0,
        "validity": 1.0,
        "consistency": 1.0,
        "accuracy": 1.0,
        "timeliness": 1.0,
    }
    assert dq_report(result)["dimension_scores"] == result.dimension_scores


def test_invalid_data_is_quarantined_with_dimension_scores(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'quality.db'}")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)

    with session_factory() as session:
        decision = DataProvenance().process(
            _payload(TransAmount="-1", Currency="GBP"),
            session,
        )
        session.commit()
        quarantine = session.query(QuarantineRecord).one()

    assert decision["decision"] == "quarantined"
    assert decision["quality"]["status"] == DataQualityStatus.FAIL
    assert quarantine.rejection_context["dq_status"] == DataQualityStatus.FAIL
    assert quarantine.rejection_context["dimension_scores"]["validity"] == 0.0