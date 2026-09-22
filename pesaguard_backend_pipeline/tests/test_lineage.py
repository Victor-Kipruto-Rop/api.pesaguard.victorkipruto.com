from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from lineage import record_lineage, trace_transaction
from models import Base


def test_lineage_trace_connects_source_and_processing_stages(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'lineage.db'}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as session:
        record_lineage(session, tenant_id="tenant-a", transaction_id="txn-1", event_id="evt-raw", stage="RAW", source="mpesa", source_event_id="MP-1", pipeline_version="p1", transformation_version="raw-1", correlation_id="corr-1")
        record_lineage(session, tenant_id="tenant-a", transaction_id="txn-1", event_id="evt-normalized", stage="NORMALIZED", source="mpesa", source_event_id="MP-1", upstream_event_id="evt-raw", pipeline_version="p1", transformation_version="norm-2", correlation_id="corr-1")
        session.commit()
        chain = trace_transaction(session, tenant_id="tenant-a", transaction_id="txn-1")
        assert [record.stage for record in chain] == ["RAW", "NORMALIZED"]
        assert chain[1].upstream_event_id == "evt-raw"
        assert chain[0].source_event_id == "MP-1"