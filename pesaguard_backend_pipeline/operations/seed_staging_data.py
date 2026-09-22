"""
Staging Database Seeding Utility for PesaGuard.

Populates staging PostgreSQL databases with realistic discrepancy anomalies, transaction
states, and audit records for staging environment validation, dashboard integration tests,
and API smoke testing.
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Resilient import handling across backend package layouts
try:
    from models import Base, Discrepancy
    from localization_utils import format_ke_currency
except ImportError:
    try:
        from pesaguard_backend_pipeline.models import Base, Discrepancy
        from pesaguard_backend_pipeline.localization_utils import format_ke_currency
    except ImportError:
        sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
        from models import Base, Discrepancy
        from localization_utils import format_ke_currency

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("pesaguard.seed_staging")

# No database fallback: staging writes require an explicitly supplied target.
STAGING_TENANT_ID = os.getenv("STAGING_TENANT_ID", "staging-tenant")


def get_engine():
    """Construct database engine for staging data seeding."""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL must be explicitly configured for staging seeding")
    return create_engine(db_url, pool_pre_ping=True)


def seed_staging_data() -> None:
    """Wipe and re-seed staging discrepancy records."""
    engine = get_engine()
    
    try:
        Base.metadata.create_all(engine)
    except Exception as exc:
        logger.warning("Database schema check notice: %s", exc)

    Session = sessionmaker(bind=engine, expire_on_commit=False)
    now = datetime.now(timezone.utc)

    records: List[Discrepancy] = [
        Discrepancy(
            id="stg-001",
            trans_id="STG-001",
            tenant_id=STAGING_TENANT_ID,
            anomaly_type="duplicate_transaction_id",
            severity="warning",
            status="needs_review",
            resolved=False,
            detected_at=now - timedelta(minutes=15),
            details={
                "trans_id": "STG-001",
                "amount": 1500.00,
                "amount_formatted": format_ke_currency(1500.00),
                "msisdn": "254700000001",
                "reason": "Duplicate Daraja callback received within 15-minute window",
            },
            notes="Automated duplicate callback flag during staging test run.",
        ),
        Discrepancy(
            id="stg-002",
            trans_id="STG-002",
            tenant_id=STAGING_TENANT_ID,
            anomaly_type="missing_payment",
            severity="critical",
            status="needs_review",
            resolved=False,
            detected_at=now - timedelta(minutes=10),
            details={
                "trans_id": "STG-002",
                "amount": 4200.00,
                "amount_formatted": format_ke_currency(4200.00),
                "msisdn": "254711000222",
                "reason": "M-Pesa callback recorded but no matching internal order reference found",
            },
            notes="Requires manual internal ledger audit.",
        ),
        Discrepancy(
            id="stg-003",
            trans_id="STG-003",
            tenant_id=STAGING_TENANT_ID,
            anomaly_type="amount_mismatch",
            severity="warning",
            status="needs_review",
            resolved=False,
            detected_at=now - timedelta(minutes=5),
            details={
                "trans_id": "STG-003",
                "received_amount": 1000.00,
                "expected_amount": 1200.00,
                "msisdn": "254722333444",
                "reason": "Partial match: Callback amount KES 1,000.00 differs from internal order KES 1,200.00",
            },
            notes="Partial payment variance flagged.",
        ),
        Discrepancy(
            id="stg-004",
            trans_id="STG-004",
            tenant_id=STAGING_TENANT_ID,
            anomaly_type="late_arriving_event",
            severity="info",
            status="resolved",
            resolved=True,
            detected_at=now - timedelta(hours=2),
            resolved_at=now - timedelta(hours=1),
            resolution_note="Auto-resolved upon late internal record sync.",
            details={
                "trans_id": "STG-004",
                "amount": 250.00,
                "amount_formatted": format_ke_currency(250.00),
                "msisdn": "254733444555",
                "reason": "Callback arrived >60 minutes after transaction timestamp",
            },
        ),
    ]

    with Session() as session:
        try:
            logger.info("Purging existing staging discrepancy data...")
            session.query(Discrepancy).delete()
            
            logger.info("Adding %d staging test discrepancies...", len(records))
            session.add_all(records)
            
            session.commit()
            logger.info("Successfully seeded staging database with dispute test fixtures!")
        except Exception as exc:
            session.rollback()
            logger.exception("Failed to seed staging database: %s", exc)
            raise


if __name__ == "__main__":
    seed_staging_data()
