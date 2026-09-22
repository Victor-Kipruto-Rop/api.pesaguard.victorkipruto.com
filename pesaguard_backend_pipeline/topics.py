"""
Central Kafka-compatible topic registry for PesaGuard and Redpanda.

Defines standardized streaming topic names, partition configurations, retention settings,
and administrative provisioning functions for producer and consumer services.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger("pesaguard.kafka_topics")

# Domain-oriented topics. Redpanda is Kafka protocol compatible, so existing
# producer/consumer clients can use this registry without a second transport.
TOPIC_TRANSACTIONS_RAW = os.getenv("PESAGUARD_TOPIC_TRANSACTIONS_RAW", "pesaguard.transactions.raw")
TOPIC_TRANSACTIONS_VALIDATED = os.getenv("PESAGUARD_TOPIC_TRANSACTIONS_VALIDATED", "pesaguard.transactions.validated")
TOPIC_TRANSACTIONS_NORMALIZED = os.getenv("PESAGUARD_TOPIC_TRANSACTIONS_NORMALIZED", "pesaguard.transactions.normalized")
TOPIC_TRANSACTIONS_ENRICHED = os.getenv("PESAGUARD_TOPIC_TRANSACTIONS_ENRICHED", "pesaguard.transactions.enriched")
TOPIC_TRANSACTIONS_PROCESSED = os.getenv("PESAGUARD_TOPIC_TRANSACTIONS_PROCESSED", "pesaguard.transactions.processed")
TOPIC_TRANSACTIONS_MATCHED = os.getenv("PESAGUARD_TOPIC_TRANSACTIONS_MATCHED", "pesaguard.reconciliation.completed")
TOPIC_DISCREPANCIES = os.getenv("PESAGUARD_TOPIC_DISCREPANCIES", "pesaguard.reconciliation.exceptions")
TOPIC_RECONCILIATION_REQUESTED = os.getenv("PESAGUARD_TOPIC_RECONCILIATION_REQUESTED", "pesaguard.reconciliation.requested")
TOPIC_DEAD_LETTERS = os.getenv("PESAGUARD_TOPIC_DEAD_LETTERS", "pesaguard.dlq")
TOPIC_AUDIT_EVENTS = os.getenv("PESAGUARD_TOPIC_AUDIT_EVENTS", "pesaguard.audit.events")
TOPIC_NOTIFICATION_EVENTS = os.getenv("PESAGUARD_TOPIC_NOTIFICATION_EVENTS", "pesaguard.notifications.requested")
TOPIC_NOTIFICATION_STATUS = os.getenv("PESAGUARD_TOPIC_NOTIFICATION_STATUS", "pesaguard.notifications.sent")
TOPIC_NOTIFICATION_FAILED = os.getenv("PESAGUARD_TOPIC_NOTIFICATION_FAILED", "pesaguard.notifications.failed")
TOPIC_WEBHOOKS_RECEIVED = os.getenv("PESAGUARD_TOPIC_WEBHOOKS_RECEIVED", "pesaguard.webhooks.received")
TOPIC_FRAUD_ANALYSIS = os.getenv("PESAGUARD_TOPIC_FRAUD_ANALYSIS", "pesaguard.fraud.analysis")
TOPIC_FRAUD_ANOMALIES = os.getenv("PESAGUARD_TOPIC_FRAUD_ANOMALIES", "pesaguard.fraud.anomalies")
TOPIC_FRAUD_DECISIONS = os.getenv("PESAGUARD_TOPIC_FRAUD_DECISIONS", "pesaguard.fraud.decisions")
TOPIC_BATCH_IMPORTS = os.getenv("PESAGUARD_TOPIC_BATCH_IMPORTS", "pesaguard.batch.imports")
TOPIC_BATCH_IMPORTS_COMPLETED = os.getenv("PESAGUARD_TOPIC_BATCH_IMPORTS_COMPLETED", "pesaguard.batch.imports.completed")
TOPIC_BATCH_IMPORTS_FAILED = os.getenv("PESAGUARD_TOPIC_BATCH_IMPORTS_FAILED", "pesaguard.batch.imports.failed")
TOPIC_RETRIES = os.getenv("PESAGUARD_TOPIC_RETRIES", "pesaguard.retries")
TOPIC_SYSTEM_EVENTS = os.getenv("PESAGUARD_TOPIC_SYSTEM_EVENTS", "pesaguard.system.events")
TOPIC_DATA_PROCESSING = os.getenv("PESAGUARD_TOPIC_DATA_PROCESSING", "pesaguard.data.processing")
TOPIC_COMMUNICATION_AUDIT = os.getenv("PESAGUARD_TOPIC_COMMUNICATION_AUDIT", "pesaguard.audit.communication")
TOPIC_TRANSACTION_RECEIVED = os.getenv("PESAGUARD_TOPIC_TRANSACTION_RECEIVED", TOPIC_TRANSACTIONS_RAW)
TOPIC_TRANSACTION_VALIDATED = TOPIC_TRANSACTIONS_VALIDATED
TOPIC_TRANSACTION_NORMALIZED = TOPIC_TRANSACTIONS_NORMALIZED
TOPIC_TRANSACTION_PROCESSED = TOPIC_TRANSACTIONS_PROCESSED
TOPIC_TRANSACTION_RECONCILED = os.getenv("PESAGUARD_TOPIC_TRANSACTION_RECONCILED", TOPIC_TRANSACTIONS_MATCHED)
TOPIC_TRANSACTION_EXCEPTION = os.getenv("PESAGUARD_TOPIC_TRANSACTION_EXCEPTION", TOPIC_DISCREPANCIES)
TOPIC_TRANSACTION_FRAUD = os.getenv("PESAGUARD_TOPIC_TRANSACTION_FRAUD", TOPIC_FRAUD_DECISIONS)

# Legacy compatibility aliases
TRANSACTIONS_RAW = TOPIC_TRANSACTIONS_RAW
TRANSACTIONS_MATCHED = TOPIC_TRANSACTIONS_MATCHED
DISCREPANCIES = TOPIC_DISCREPANCIES

ALL_TOPICS: List[str] = [
    TOPIC_TRANSACTIONS_RAW,
    TOPIC_TRANSACTIONS_VALIDATED,
    TOPIC_TRANSACTIONS_NORMALIZED,
    TOPIC_TRANSACTIONS_ENRICHED,
    TOPIC_TRANSACTIONS_PROCESSED,
    TOPIC_TRANSACTIONS_MATCHED,
    TOPIC_DISCREPANCIES,
    TOPIC_RECONCILIATION_REQUESTED,
    TOPIC_DEAD_LETTERS,
    TOPIC_AUDIT_EVENTS,
    TOPIC_NOTIFICATION_EVENTS,
    TOPIC_NOTIFICATION_STATUS,
    TOPIC_NOTIFICATION_FAILED,
    TOPIC_WEBHOOKS_RECEIVED,
    TOPIC_FRAUD_ANALYSIS,
    TOPIC_FRAUD_ANOMALIES,
    TOPIC_FRAUD_DECISIONS,
    TOPIC_BATCH_IMPORTS,
    TOPIC_BATCH_IMPORTS_COMPLETED,
    TOPIC_BATCH_IMPORTS_FAILED,
    TOPIC_RETRIES,
    TOPIC_SYSTEM_EVENTS,
    TOPIC_DATA_PROCESSING,
    TOPIC_COMMUNICATION_AUDIT,
    TOPIC_TRANSACTION_VALIDATED,
    TOPIC_TRANSACTION_FRAUD,
]

EVENT_TYPE_TOPICS = {
    "transaction.created": TOPIC_TRANSACTION_RECEIVED,
    "transaction.received": TOPIC_TRANSACTION_RECEIVED,
    "transaction.validated": TOPIC_TRANSACTION_VALIDATED,
    "transaction.normalized": TOPIC_TRANSACTION_NORMALIZED,
    "transaction.enriched": TOPIC_TRANSACTIONS_ENRICHED,
    "transaction.processed": TOPIC_TRANSACTION_PROCESSED,
    "transaction.reconciled": TOPIC_TRANSACTION_RECONCILED,
    "transaction.exception_created": TOPIC_TRANSACTION_EXCEPTION,
    "transaction.fraud_detected": TOPIC_TRANSACTION_FRAUD,
    "reconciliation.requested": TOPIC_RECONCILIATION_REQUESTED,
    "reconciliation.completed": TOPIC_TRANSACTIONS_MATCHED,
    "reconciliation.exception": TOPIC_DISCREPANCIES,
    "fraud.analysis_requested": TOPIC_FRAUD_ANALYSIS,
    "fraud.anomaly_detected": TOPIC_FRAUD_ANOMALIES,
    "fraud.decision_created": TOPIC_FRAUD_DECISIONS,
    "notification.requested": TOPIC_NOTIFICATION_EVENTS,
    "notification.sent": TOPIC_NOTIFICATION_STATUS,
    "notification.failed": TOPIC_NOTIFICATION_FAILED,
    "webhook.received": TOPIC_WEBHOOKS_RECEIVED,
    "batch_import.received": TOPIC_BATCH_IMPORTS,
    "batch_import.completed": TOPIC_BATCH_IMPORTS_COMPLETED,
    "batch_import.failed": TOPIC_BATCH_IMPORTS_FAILED,
    "event.retry_scheduled": TOPIC_RETRIES,
    "system.event": TOPIC_SYSTEM_EVENTS,
    "data_processing.event": TOPIC_DATA_PROCESSING,
}

# Production Topic Provisioning Specifications
# Production deployments should set KAFKA_REPLICATION_FACTOR explicitly (normally 2+).
KAFKA_REPLICATION_FACTOR = int(os.getenv("KAFKA_REPLICATION_FACTOR", "2"))

# Retentions expressed in milliseconds (7 days = 604,800,000 ms)
TOPIC_SPECIFICATIONS: Dict[str, Dict[str, Any]] = {
    TOPIC_TRANSACTIONS_RAW: {
        "num_partitions": int(os.getenv("KAFKA_PARTITIONS_RAW", "6")),
        "replication_factor": KAFKA_REPLICATION_FACTOR,
        "configs": {
            "retention.ms": "604800000",  # 7 Days retention
            "cleanup.policy": "delete",
        },
    },
    TOPIC_TRANSACTIONS_MATCHED: {
        "num_partitions": int(os.getenv("KAFKA_PARTITIONS_MATCHED", "3")),
        "replication_factor": KAFKA_REPLICATION_FACTOR,
        "configs": {
            "retention.ms": "2592000000",  # 30 Days retention
            "cleanup.policy": "delete",
        },
    },
    TOPIC_TRANSACTION_VALIDATED: {
        "num_partitions": int(os.getenv("KAFKA_PARTITIONS_VALIDATED", "6")),
        "replication_factor": KAFKA_REPLICATION_FACTOR,
        "configs": {"retention.ms": "604800000", "cleanup.policy": "delete"},
    },
    TOPIC_TRANSACTIONS_NORMALIZED: {
        "num_partitions": int(os.getenv("KAFKA_PARTITIONS_NORMALIZED", "6")),
        "replication_factor": KAFKA_REPLICATION_FACTOR,
        "configs": {"retention.ms": "604800000", "cleanup.policy": "delete"},
    },
    TOPIC_TRANSACTIONS_PROCESSED: {
        "num_partitions": int(os.getenv("KAFKA_PARTITIONS_PROCESSED", "6")),
        "replication_factor": KAFKA_REPLICATION_FACTOR,
        "configs": {"retention.ms": "2592000000", "cleanup.policy": "delete"},
    },
    TOPIC_DISCREPANCIES: {
        "num_partitions": int(os.getenv("KAFKA_PARTITIONS_DISCREPANCIES", "3")),
        "replication_factor": KAFKA_REPLICATION_FACTOR,
        "configs": {
            "retention.ms": "7776000000",  # 90 Days retention
            "cleanup.policy": "delete",
        },
    },
    TOPIC_TRANSACTION_FRAUD: {
        "num_partitions": int(os.getenv("KAFKA_PARTITIONS_FRAUD", "3")),
        "replication_factor": KAFKA_REPLICATION_FACTOR,
        "configs": {"retention.ms": "2592000000", "cleanup.policy": "delete"},
    },
    TOPIC_DEAD_LETTERS: {
        "num_partitions": 3,
        "replication_factor": KAFKA_REPLICATION_FACTOR,
        "configs": {
            "retention.ms": "2592000000",  # 30 Days retention
        },
    },
    TOPIC_AUDIT_EVENTS: {
        "num_partitions": 3,
        "replication_factor": KAFKA_REPLICATION_FACTOR,
        "configs": {
            "retention.ms": "31536000000",  # 365 Days retention
        },
    },
    TOPIC_NOTIFICATION_EVENTS: {
        "num_partitions": 3,
        "replication_factor": KAFKA_REPLICATION_FACTOR,
        "configs": {"retention.ms": "2592000000"},
    },
    TOPIC_NOTIFICATION_STATUS: {
        "num_partitions": 3,
        "replication_factor": KAFKA_REPLICATION_FACTOR,
        "configs": {"retention.ms": "2592000000"},
    },
    TOPIC_COMMUNICATION_AUDIT: {
        "num_partitions": 3,
        "replication_factor": KAFKA_REPLICATION_FACTOR,
        "configs": {"retention.ms": "31536000000"},
    },
}

# Ensure every registered domain topic is provisioned, including topics added
# by the event contract without requiring a second hand-maintained inventory.
for _topic in ALL_TOPICS:
    TOPIC_SPECIFICATIONS.setdefault(
        _topic,
        {
            "num_partitions": int(os.getenv("KAFKA_PARTITIONS_DEFAULT", "3")),
            "replication_factor": KAFKA_REPLICATION_FACTOR,
            "configs": {"retention.ms": "2592000000", "cleanup.policy": "delete"},
        },
    )


def provision_topics(bootstrap_servers: Optional[str] = None) -> bool:
    """
    Ensure all required PesaGuard Kafka topics exist in the target cluster.
    Creates missing topics based on `TOPIC_SPECIFICATIONS`.

    Args:
        bootstrap_servers: Comma-separated Kafka broker addresses.

    Returns:
        True if all topics were provisioned or already exist, False on failure.
    """
    servers = bootstrap_servers or os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

    try:
        try:
            from kafka.admin import KafkaAdminClient, NewTopic
        except ImportError:
            try:
                from kafka import KafkaAdminClient
                from kafka.admin import NewTopic
            except ImportError:
                logger.warning("KafkaAdminClient dependencies unavailable. Skipping topic auto-provisioning.")
                return False

        admin_client = KafkaAdminClient(
            bootstrap_servers=servers,
            client_id="pesaguard-topic-provisioner",
            request_timeout_ms=10000,
        )

        existing_topics = set(admin_client.list_topics())
        cluster = admin_client.describe_cluster()
        broker_count = max(1, len(cluster.get("brokers", [])))
        replication_factor = min(KAFKA_REPLICATION_FACTOR, broker_count)
        new_topics: List[NewTopic] = []

        for topic_name, spec in TOPIC_SPECIFICATIONS.items():
            if topic_name not in existing_topics:
                new_topics.append(
                    NewTopic(
                        name=topic_name,
                        num_partitions=spec["num_partitions"],
                        replication_factor=min(spec["replication_factor"], replication_factor),
                        topic_configs=spec.get("configs", {}),
                    )
                )

        if new_topics:
            logger.info("Creating %d missing Kafka topic(s): %s", len(new_topics), [t.name for t in new_topics])
            admin_client.create_topics(new_topics=new_topics, validate_only=False)
            logger.info("Successfully provisioned Kafka topics on %s", servers)
        else:
            logger.info("All PesaGuard Kafka topics already exist on %s", servers)

        admin_client.close()
        return True

    except Exception as exc:
        logger.exception("Failed to provision Kafka topics on broker '%s': %s", servers, exc)
        return False


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    print(f"PesaGuard Kafka Topic Inventory:")
    for t in ALL_TOPICS:
        spec = TOPIC_SPECIFICATIONS.get(t, {})
        print(f"  - {t:30s} [Partitions: {spec.get('num_partitions', 1)}, Replication: {spec.get('replication_factor', 1)}]")
    
    if len(sys.argv) > 1 and sys.argv[1] == "--provision":
        provision_topics()
