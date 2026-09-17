"""
Data Retention Cleanup Job for PesaGuard Operational Data.

Purges expired raw transactions, reconciled discrepancies, dead letters, and audit logs
based on tenant-configurable retention policies to comply with data privacy regulations
and optimize PostgreSQL storage footprint.
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from sqlalchemy import and_, create_engine, delete, func, or_, select
from sqlalchemy.orm import sessionmaker

# Resilient import handling across package layouts
try:
    from models import Base, DeadLetter, Discrepancy, ProcessedTransaction, ReconciliationOutbox, Transaction, TransactionOutbox
    from action_audit import ActionAuditEntry, AuditLegalHold
except ImportError:
    try:
        from pesaguard_backend_pipeline.models import Base, DeadLetter, Discrepancy, ProcessedTransaction, ReconciliationOutbox, Transaction, TransactionOutbox
        from pesaguard_backend_pipeline.action_audit import ActionAuditEntry, AuditLegalHold
    except ImportError:
        sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
        from models import Base, DeadLetter, Discrepancy, ProcessedTransaction, ReconciliationOutbox, Transaction, TransactionOutbox
        from action_audit import ActionAuditEntry, AuditLegalHold

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("pesaguard.retention_cleanup")

def get_database_url() -> str:
    return os.getenv("DATABASE_URL", "postgresql://pesaguard:pesaguard@localhost:5432/pesaguard")

# Default Retention Windows (in days)
RETENTION_DAYS_TRANSACTIONS = int(os.getenv("PESAGUARD_RETENTION_DAYS_TRANSACTIONS", "90"))
RETENTION_DAYS_DISCREPANCIES = int(os.getenv("PESAGUARD_RETENTION_DAYS_DISCREPANCIES", "180"))
RETENTION_DAYS_DEAD_LETTERS = int(os.getenv("PESAGUARD_RETENTION_DAYS_DEAD_LETTERS", "30"))
RETENTION_DAYS_AUDIT = int(os.getenv("PESAGUARD_RETENTION_DAYS_AUDIT", "365"))

# Deletion batch size to prevent long-lived table locks and WAL bloat
BATCH_SIZE = int(os.getenv("PESAGUARD_RETENTION_BATCH_SIZE", "1000"))


def get_engine():
    """Construct database engine instance with connection pooling."""
    engine = create_engine(
        get_database_url(),
        pool_pre_ping=True,
        connect_args={"connect_timeout": 10} if get_database_url().startswith("postgresql") else {},
    )
    try:
        from metrics import instrument_engine_query_timing
        instrument_engine_query_timing(engine)
    except Exception:
        logger.debug("Retention cleanup engine query timing instrumentation skipped.", exc_info=True)
    return engine


def get_session_factory():
    """Return ORM session factory."""
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def _hold_exclusion(model, now: datetime):
    resource_columns = [column for column in (
        getattr(model, "id", None), getattr(model, "trans_id", None),
        getattr(model, "daraja_trans_id", None), getattr(model, "event_key", None),
    ) if column is not None]
    resource_match = and_(
        AuditLegalHold.scope_type.in_(["resource", "transaction"]),
        or_(*[AuditLegalHold.scope_id == column for column in resource_columns]),
    ) if resource_columns else False
    return ~select(AuditLegalHold.id).where(
        AuditLegalHold.tenant_id == model.tenant_id,
        AuditLegalHold.active.is_(True),
        or_(AuditLegalHold.expires_at.is_(None), AuditLegalHold.expires_at > now),
        or_(AuditLegalHold.scope_type == "tenant", resource_match),
    ).correlate(model).exists()


def _delete_in_batches(session, model, time_column, cutoff_dt: datetime, tenant_id: Optional[str] = None, dry_run: bool = False, extra_filter=None) -> int:
    """Safely purge records older than cutoff timestamp in small transaction chunks."""
    total_deleted = 0

    while True:
        # Construct primary key subquery for batch deletion
        eligibility = [time_column < cutoff_dt, _hold_exclusion(model, datetime.now(timezone.utc))]
        if extra_filter is not None:
            eligibility.append(extra_filter)
        subquery = select(model.id if hasattr(model, "id") else model.trans_id).where(*eligibility)
        if tenant_id and hasattr(model, "tenant_id"):
            subquery = subquery.where(model.tenant_id == tenant_id)

        subquery = subquery.limit(BATCH_SIZE)

        if dry_run:
            count_query = select(func.count()).select_from(model).where(*eligibility)
            if tenant_id and hasattr(model, "tenant_id"):
                count_query = count_query.where(model.tenant_id == tenant_id)
            return session.scalar(count_query) or 0

        # Execute chunked deletion
        if hasattr(model, "id"):
            stmt = delete(model).where(model.id.in_(subquery))
        else:
            stmt = delete(model).where(model.trans_id.in_(subquery))

        result = session.execute(stmt)
        rows_affected = result.rowcount
        session.commit()

        total_deleted += rows_affected
        if rows_affected < BATCH_SIZE:
            break

    return total_deleted


def _count_audit_archival_candidates(session, cutoff_dt: datetime, tenant_id: Optional[str] = None) -> int:
    """Count expired audit rows eligible for archival without mutating append-only logs."""
    base_filter = [
        ActionAuditEntry.created_at < cutoff_dt,
        ~select(AuditLegalHold.id).where(
            AuditLegalHold.tenant_id == ActionAuditEntry.tenant_id,
            AuditLegalHold.active.is_(True),
            or_(AuditLegalHold.expires_at.is_(None), AuditLegalHold.expires_at > datetime.now(timezone.utc)),
            or_(
                AuditLegalHold.scope_type == "tenant",
                and_(AuditLegalHold.scope_type == ActionAuditEntry.resource_type, AuditLegalHold.scope_id == ActionAuditEntry.resource_id),
            ),
        ).correlate(ActionAuditEntry).exists(),
    ]
    if tenant_id:
        base_filter.append(ActionAuditEntry.tenant_id == tenant_id)

    return session.scalar(select(func.count()).select_from(ActionAuditEntry).where(*base_filter)) or 0


def cleanup_retention(tenant_id: Optional[str] = None, dry_run: bool = False) -> Dict[str, Any]:
    """Execute retention policy cleanup across operational tables.

    Args:
        tenant_id: Optional tenant filter to target specific tenant data.
        dry_run: If True, returns estimated counts without deleting rows.

    Returns:
        Telemetry summary dict with deleted record counts.
    """
    now = datetime.now(timezone.utc)
    oldest_transaction = now - timedelta(days=RETENTION_DAYS_TRANSACTIONS)
    oldest_discrepancy = now - timedelta(days=RETENTION_DAYS_DISCREPANCIES)
    oldest_dead_letter = now - timedelta(days=RETENTION_DAYS_DEAD_LETTERS)
    oldest_audit = now - timedelta(days=RETENTION_DAYS_AUDIT)

    logger.info(
        "Starting data retention cleanup (dry_run=%s, tenant_id=%s)...",
        dry_run, tenant_id or "all"
    )

    cleanup_engine = get_engine()
    SessionLocal = sessionmaker(bind=cleanup_engine, expire_on_commit=False)
    session = SessionLocal()

    try:
        deleted_transactions = _delete_in_batches(
            session, Transaction, Transaction.created_at, oldest_transaction, tenant_id, dry_run
        )
        deleted_processed = _delete_in_batches(
            session, ProcessedTransaction, ProcessedTransaction.received_at, oldest_transaction, tenant_id, dry_run
        )
        deleted_discrepancies = _delete_in_batches(
            session, Discrepancy, Discrepancy.detected_at, oldest_discrepancy, tenant_id, dry_run
        )
        deleted_dead_letters = _delete_in_batches(
            session, DeadLetter, DeadLetter.created_at, oldest_dead_letter, tenant_id, dry_run
        )
        deleted_transaction_outbox = _delete_in_batches(
            session, TransactionOutbox, TransactionOutbox.created_at, oldest_transaction, tenant_id, dry_run,
            TransactionOutbox.status == "published",
        )
        deleted_reconciliation_outbox = _delete_in_batches(
            session, ReconciliationOutbox, ReconciliationOutbox.created_at, oldest_discrepancy, tenant_id, dry_run,
            ReconciliationOutbox.status == "published",
        )
        eligible_audit_entries = _count_audit_archival_candidates(session, oldest_audit, tenant_id)
        # Audit rows are append-only by database policy. A separate archival
        # exporter must move eligible rows before any future purge capability.
        deleted_audit = 0

        def post_delete_count(model, time_column, cutoff_dt, extra_filter=None):
            filters = [time_column < cutoff_dt]
            if tenant_id and hasattr(model, "tenant_id"):
                filters.append(model.tenant_id == tenant_id)
            if extra_filter is not None:
                filters.append(extra_filter)
            return session.scalar(select(func.count()).select_from(model).where(*filters)) or 0

        metrics = {
            "status": "success",
            "dry_run": dry_run,
            "tenant_id": tenant_id or "all",
            "deleted_transactions": deleted_transactions,
            "deleted_processed_transactions": deleted_processed,
            "deleted_discrepancies": deleted_discrepancies,
            "deleted_dead_letters": deleted_dead_letters,
            "deleted_transaction_outbox": deleted_transaction_outbox,
            "deleted_reconciliation_outbox": deleted_reconciliation_outbox,
            "deleted_audit_entries": deleted_audit,
            "deleted_audit": deleted_audit,
            "eligible_audit_entries": eligible_audit_entries,
            "post_delete_counts": {
                "transactions": post_delete_count(Transaction, Transaction.created_at, oldest_transaction),
                "processed_transactions": post_delete_count(ProcessedTransaction, ProcessedTransaction.received_at, oldest_transaction),
                "discrepancies": post_delete_count(Discrepancy, Discrepancy.detected_at, oldest_discrepancy),
                "dead_letters": post_delete_count(DeadLetter, DeadLetter.created_at, oldest_dead_letter),
                "transaction_outbox": post_delete_count(TransactionOutbox, TransactionOutbox.created_at, oldest_transaction, TransactionOutbox.status == "published"),
                "reconciliation_outbox": post_delete_count(ReconciliationOutbox, ReconciliationOutbox.created_at, oldest_discrepancy, ReconciliationOutbox.status == "published"),
            },
            "retention_windows": {
                "transactions_days": RETENTION_DAYS_TRANSACTIONS,
                "discrepancies_days": RETENTION_DAYS_DISCREPANCIES,
                "dead_letters_days": RETENTION_DAYS_DEAD_LETTERS,
                "audit_days": RETENTION_DAYS_AUDIT,
            },
        }

        logger.info("Retention cleanup finished cleanly: %s", metrics)
        return metrics

    except Exception as exc:
        session.rollback()
        logger.exception("Data retention cleanup job failed: %s", exc)
        raise
    finally:
        session.close()
        cleanup_engine.dispose()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="PesaGuard Data Retention Cleanup Utility")
    parser.add_argument("--dry-run", action="store_true", help="Preview row counts without performing deletions")
    parser.add_argument("--tenant-id", type=str, help="Scope deletion to a specific tenant ID")
    args = parser.parse_args()

    engine = get_engine()
    result_summary = cleanup_retention(tenant_id=args.tenant_id, dry_run=args.dry_run)
    print("Retention Cleanup Summary:")
    for key, val in result_summary.items():
        print(f"  {key}: {val}")
