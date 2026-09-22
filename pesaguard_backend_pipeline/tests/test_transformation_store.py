from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import Base, TransformationRecord
from transformation_store import record_transformation_stage


def test_transformation_records_are_append_only_and_replay_safe(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'stages.db'}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as session:
        raw = record_transformation_stage(
            session,
            tenant_id="tenant-a",
            transaction_id="txn-1",
            event_id="evt-raw",
            stage="RAW",
            payload={"amount": "1,500"},
        )
        validated = record_transformation_stage(
            session,
            tenant_id="tenant-a",
            transaction_id="txn-1",
            event_id="evt-validated",
            stage="VALIDATED",
            payload={"amount": "1500.00"},
            source_event_id="evt-raw",
        )
        replay = record_transformation_stage(
            session,
            tenant_id="tenant-a",
            transaction_id="txn-1",
            event_id="evt-raw",
            stage="RAW",
            payload={"amount": "corrupted"},
        )
        session.commit()
        assert replay.id == raw.id
        assert replay.payload == {"amount": "1,500"}
        assert validated.source_event_id == "evt-raw"
        assert session.query(TransformationRecord).count() == 2