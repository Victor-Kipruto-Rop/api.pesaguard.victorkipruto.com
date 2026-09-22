from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from aggregation_service import aggregate_transactions, update_merchant_metrics
from models import Base, MerchantMetric


def test_aggregate_transactions_builds_dashboard_metrics():
    metrics = aggregate_transactions([
        {"merchant_id": "merchant-1", "amount": "5000.00", "status": "COMPLETED"},
        {"merchant_id": "merchant-1", "amount": "1000.00", "status": "FAILED"},
        {"merchant_id": "merchant-1", "amount": "250.00", "status": "RECONCILED", "anomaly": True},
    ])
    merchant = metrics["merchant-1"]
    assert merchant.transaction_count == 3
    assert merchant.total_volume == Decimal("6250.00")
    assert merchant.average_transaction == Decimal("2083.33")
    assert merchant.failed_transactions == 1
    assert merchant.reconciled_transactions == 2
    assert merchant.anomaly_count == 1
    assert merchant.failure_rate == 1 / 3


def test_incremental_metrics_persist_hour_day_and_week_buckets(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'metrics.db'}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as session:
        update_merchant_metrics(
            session,
            {
                "merchant_id": "merchant-1",
                "amount": "5000.00",
                "status": "COMPLETED",
                "transaction_time": "2026-09-23T10:15:00Z",
            },
            tenant_id="tenant-a",
        )
        session.commit()
        assert session.query(MerchantMetric).count() == 3
        day = session.query(MerchantMetric).filter_by(tenant_id="tenant-a", granularity="day").one()
        assert day.total_volume == Decimal("5000.00")
        assert day.reconciled_transactions == 1