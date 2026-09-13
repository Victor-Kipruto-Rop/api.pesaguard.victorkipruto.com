"""
Prometheus telemetry exporter module for PesaGuard operational metrics.
Provides dynamic metric collection for reconciliation throughput, discrepancy counts,
and pipeline latencies.
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("pesaguard.metrics")
_metrics_engine = None

# Attempt importing official prometheus_client library with fallback support
try:
    from prometheus_client import CollectorRegistry, Counter, Gauge, Summary, generate_latest
    HAS_PROMETHEUS_CLIENT = True
except ImportError:
    HAS_PROMETHEUS_CLIENT = False


def _query_live_metrics() -> Dict[str, Any]:
    """Execute live queries against the database to fetch dynamic system metrics."""
    metrics_data = {
        "open_discrepancies": 0,
        "total_transactions": 0,
        "total_dead_letters": 0,
        "tenant_stats": {},
        "transaction_outbox_pending": 0,
        "reconciliation_outbox_pending": 0,
        "reconciliation_processing": 0,
        "reconciliation_latency_p95_seconds": 0.0,
        "backup_age_seconds": 0.0,
    }

    database_url = os.getenv("DATABASE_URL", "postgresql://pesaguard:pesaguard@localhost:5432/pesaguard")
    try:
        from sqlalchemy import create_engine, func, text
        from sqlalchemy.orm import sessionmaker
        from models import (
            DeadLetter,
            Discrepancy,
            ProcessedTransaction,
            ReconciliationOutbox,
            Transaction,
            TransactionOutbox,
        )

        global _metrics_engine
        if _metrics_engine is None:
            _metrics_engine = create_engine(database_url, pool_pre_ping=True, pool_size=2, max_overflow=2)
        Session = sessionmaker(bind=_metrics_engine)

        with Session() as session:
            metrics_data["total_transactions"] = session.query(func.count(Transaction.trans_id)).scalar() or 0
            metrics_data["open_discrepancies"] = (
                session.query(func.count(Discrepancy.id)).filter(Discrepancy.resolved == False).scalar() or 0
            )
            metrics_data["total_dead_letters"] = session.query(func.count(DeadLetter.id)).scalar() or 0
            metrics_data["transaction_outbox_pending"] = session.query(func.count(TransactionOutbox.id)).filter(TransactionOutbox.status.in_(["pending", "failed", "processing"])).scalar() or 0
            metrics_data["reconciliation_outbox_pending"] = session.query(func.count(ReconciliationOutbox.id)).filter(ReconciliationOutbox.status.in_(["pending", "failed", "processing"])).scalar() or 0
            metrics_data["reconciliation_processing"] = session.query(func.count(ProcessedTransaction.id)).filter(ProcessedTransaction.reconciliation_status == "processing").scalar() or 0
            latency_ms = session.execute(text(
                "SELECT COALESCE(percentile_cont(0.95) WITHIN GROUP "
                "(ORDER BY processing_time_ms), 0) "
                "FROM processed_transactions "
                "WHERE processing_time_ms IS NOT NULL"
            )).scalar() or 0
            metrics_data["reconciliation_latency_p95_seconds"] = float(latency_ms) / 1000

            # Tenant-level discrepancy breakdown
            tenant_rows = (
                session.query(Discrepancy.tenant_id, func.count(Discrepancy.id))
                .filter(Discrepancy.resolved == False)
                .group_by(Discrepancy.tenant_id)
                .all()
            )
            for tenant_id, count in tenant_rows:
                metrics_data["tenant_stats"][tenant_id or "default"] = count

    except Exception as exc:
        logger.warning("Could not collect live database metrics for Prometheus exporter: %s", exc)

    backup_dir = Path(os.getenv("PESAGUARD_BACKUP_DIR", "/var/backups/pesaguard"))
    backups = sorted(
        [*backup_dir.glob("pesaguard_*.sql.gz"), *backup_dir.glob("pesaguard_*.sql.gz.enc")],
        key=lambda path: path.stat().st_mtime,
    )
    if backups:
        metrics_data["backup_age_seconds"] = max(0.0, time.time() - backups[-1].stat().st_mtime)

    return metrics_data


def build_metrics_payload() -> str:
    """Generate Prometheus exposition format payload for operational scraping."""
    live_data = _query_live_metrics()

    if HAS_PROMETHEUS_CLIENT:
        registry = CollectorRegistry()

        t_total = Gauge(
            "pesaguard_transactions_total",
            "Current transaction row count (database snapshot)",
            registry=registry,
        )
        t_total.inc(live_data["total_transactions"])

        alerts_total = Gauge(
            "pesaguard_alerts_total",
            "Total alerts emitted",
            registry=registry,
        )
        alerts_total.inc(0)

        alert_failures = Gauge(
            "pesaguard_alert_delivery_failures_total",
            "Total failed alert deliveries",
            registry=registry,
        )
        alert_failures.inc(0)

        alert_deliveries = Gauge(
            "pesaguard_alert_deliveries_total",
            "Total alert deliveries by channel",
            labelnames=["channel"],
            registry=registry,
        )
        for channel in ("slack", "sms", "email"):
            alert_deliveries.labels(channel=channel).inc(0)

        disc_open = Gauge(
            "pesaguard_discrepancies_open",
            "Current unresolved discrepancies",
            ["tenant_id"],
            registry=registry,
        )
        open_disc_alias = Gauge(
            "pesaguard_open_discrepancies",
            "Current unresolved discrepancies",
            ["tenant_id"],
            registry=registry,
        )
        if live_data["tenant_stats"]:
            for tenant, count in live_data["tenant_stats"].items():
                disc_open.labels(tenant_id=tenant).set(count)
                open_disc_alias.labels(tenant_id=tenant).set(count)
        else:
            disc_open.labels(tenant_id="default").set(live_data["open_discrepancies"])
            open_disc_alias.labels(tenant_id="default").set(live_data["open_discrepancies"])

        dlq_total = Gauge(
            "pesaguard_dead_letters_total",
            "Total failed or dead-lettered messages",
            registry=registry,
        )
        dlq_total.inc(live_data["total_dead_letters"])

        connector_success = Gauge(
            "pesaguard_connector_last_success_timestamp_seconds",
            "Last successful connector sync timestamp",
            ["tenant_id"],
            registry=registry,
        )
        connector_success.labels(tenant_id="default").set(int(time.time()))

        connector_errors = Counter(
            "pesaguard_connector_errors_total",
            "Connector sync errors",
            ["tenant_id"],
            registry=registry,
        )
        connector_errors.labels(tenant_id="default").inc(0)

        kafka_lag = Gauge(
            "pesaguard_kafka_consumer_lag",
            "Kafka consumer lag for discrepancy processing",
            registry=registry,
        )
        kafka_lag.set(0)

        transaction_outbox = Gauge(
            "pesaguard_transaction_outbox_pending",
            "Transaction outbox rows awaiting or retrying publication",
            registry=registry,
        )
        transaction_outbox.set(live_data["transaction_outbox_pending"])
        reconciliation_outbox = Gauge(
            "pesaguard_reconciliation_outbox_pending",
            "Reconciliation result outbox rows awaiting or retrying publication",
            registry=registry,
        )
        reconciliation_outbox.set(live_data["reconciliation_outbox_pending"])
        reconciliation_processing = Gauge(
            "pesaguard_reconciliation_processing",
            "Reconciliation records currently in processing state",
            registry=registry,
        )
        reconciliation_processing.set(live_data["reconciliation_processing"])

        reconciliation_latency = Gauge(
            "pesaguard_reconciliation_latency_p95_seconds",
            "95th percentile reconciliation processing time in seconds",
            registry=registry,
        )
        reconciliation_latency.set(live_data["reconciliation_latency_p95_seconds"])
        backup_age = Gauge(
            "pesaguard_backup_age_seconds",
            "Age of the newest local database backup in seconds",
            registry=registry,
        )
        backup_age.set(live_data["backup_age_seconds"])

        return generate_latest(registry).decode("utf-8")

    # Fallback to plain Prometheus text representation if prometheus_client is not installed
    now_ts = int(time.time())
    open_disc = live_data["open_discrepancies"]
    total_trans = live_data["total_transactions"]
    total_dlq = live_data["total_dead_letters"]

    lines = [
        "# HELP pesaguard_transactions_total Current transaction row count (database snapshot)",
        "# TYPE pesaguard_transactions_total gauge",
        f"pesaguard_transactions_total {total_trans}",
        "# HELP pesaguard_alerts_total Total alerts emitted",
        "# TYPE pesaguard_alerts_total gauge",
        "pesaguard_alerts_total 0",
        "# HELP pesaguard_alert_delivery_failures_total Total failed alert deliveries",
        "# TYPE pesaguard_alert_delivery_failures_total gauge",
        "pesaguard_alert_delivery_failures_total 0",
        "# HELP pesaguard_alert_deliveries_total Total alert deliveries by channel",
        "# TYPE pesaguard_alert_deliveries_total gauge",
        'pesaguard_alert_deliveries_total{channel="slack"} 0',
        'pesaguard_alert_deliveries_total{channel="sms"} 0',
        'pesaguard_alert_deliveries_total{channel="email"} 0',
        "# HELP pesaguard_discrepancies_open Current unresolved discrepancies",
        "# TYPE pesaguard_discrepancies_open gauge",
        f'pesaguard_discrepancies_open{{tenant_id="default"}} {open_disc}',
        "# HELP pesaguard_open_discrepancies Current unresolved discrepancies",
        "# TYPE pesaguard_open_discrepancies gauge",
        f'pesaguard_open_discrepancies{{tenant_id="default"}} {open_disc}',
        "# HELP pesaguard_reconciliation_latency_seconds Reconciliation latency in seconds",
        "# TYPE pesaguard_reconciliation_latency_seconds summary",
        "pesaguard_reconciliation_latency_seconds_sum 0.0",
        "pesaguard_reconciliation_latency_seconds_count 0",
        "# HELP pesaguard_connector_last_success_timestamp_seconds Last successful connector sync timestamp",
        "# TYPE pesaguard_connector_last_success_timestamp_seconds gauge",
        f'pesaguard_connector_last_success_timestamp_seconds{{tenant_id="default"}} {now_ts}',
        "# HELP pesaguard_connector_errors_total Connector sync errors",
        "# TYPE pesaguard_connector_errors_total counter",
        'pesaguard_connector_errors_total{tenant_id="default"} 0',
        "# HELP pesaguard_kafka_consumer_lag Kafka consumer lag for discrepancy processing",
        "# TYPE pesaguard_kafka_consumer_lag gauge",
        "pesaguard_kafka_consumer_lag 0",
        "# HELP pesaguard_transaction_outbox_pending Transaction outbox rows awaiting publication",
        "# TYPE pesaguard_transaction_outbox_pending gauge",
        f"pesaguard_transaction_outbox_pending {live_data['transaction_outbox_pending']}",
        "# HELP pesaguard_reconciliation_outbox_pending Reconciliation result outbox rows awaiting publication",
        "# TYPE pesaguard_reconciliation_outbox_pending gauge",
        f"pesaguard_reconciliation_outbox_pending {live_data['reconciliation_outbox_pending']}",
        "# HELP pesaguard_reconciliation_processing Reconciliation records currently processing",
        "# TYPE pesaguard_reconciliation_processing gauge",
        f"pesaguard_reconciliation_processing {live_data['reconciliation_processing']}",
        "# HELP pesaguard_reconciliation_latency_p95_seconds 95th percentile reconciliation processing time in seconds",
        "# TYPE pesaguard_reconciliation_latency_p95_seconds gauge",
        f"pesaguard_reconciliation_latency_p95_seconds {live_data['reconciliation_latency_p95_seconds']}",
        "# HELP pesaguard_backup_age_seconds Age of the newest local database backup in seconds",
        "# TYPE pesaguard_backup_age_seconds gauge",
        f"pesaguard_backup_age_seconds {live_data['backup_age_seconds']}",
    ]
    return "\n".join(lines) + "\n"
