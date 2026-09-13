"""
Central Kafka Topic Registry & Provisioning Utility for PesaGuard.

Defines standardized streaming topic names, partition configurations, retention settings,
and administrative provisioning functions for producer and consumer services.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger("pesaguard.kafka_topics")

# Standard Topic Definitions (Configurable via Environment Variables)
TOPIC_TRANSACTIONS_RAW = os.getenv("PESAGUARD_TOPIC_TRANSACTIONS_RAW", "mpesa.transactions.raw")
TOPIC_TRANSACTIONS_MATCHED = os.getenv("PESAGUARD_TOPIC_TRANSACTIONS_MATCHED", "mpesa.transactions.matched")
TOPIC_DISCREPANCIES = os.getenv("PESAGUARD_TOPIC_DISCREPANCIES", "mpesa.discrepancies")
TOPIC_DEAD_LETTERS = os.getenv("PESAGUARD_TOPIC_DEAD_LETTERS", "mpesa.dead_letters")
TOPIC_AUDIT_EVENTS = os.getenv("PESAGUARD_TOPIC_AUDIT_EVENTS", "mpesa.audit.events")
TOPIC_NOTIFICATION_EVENTS = os.getenv("PESAGUARD_TOPIC_NOTIFICATION_EVENTS", "notification.events")
TOPIC_NOTIFICATION_STATUS = os.getenv("PESAGUARD_TOPIC_NOTIFICATION_STATUS", "notification.status")
TOPIC_COMMUNICATION_AUDIT = os.getenv("PESAGUARD_TOPIC_COMMUNICATION_AUDIT", "communication.audit")

# Legacy compatibility aliases
TRANSACTIONS_RAW = TOPIC_TRANSACTIONS_RAW
TRANSACTIONS_MATCHED = TOPIC_TRANSACTIONS_MATCHED
DISCREPANCIES = TOPIC_DISCREPANCIES

ALL_TOPICS: List[str] = [
    TOPIC_TRANSACTIONS_RAW,
    TOPIC_TRANSACTIONS_MATCHED,
    TOPIC_DISCREPANCIES,
    TOPIC_DEAD_LETTERS,
    TOPIC_AUDIT_EVENTS,
    TOPIC_NOTIFICATION_EVENTS,
    TOPIC_NOTIFICATION_STATUS,
    TOPIC_COMMUNICATION_AUDIT,
]

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
    TOPIC_DISCREPANCIES: {
        "num_partitions": int(os.getenv("KAFKA_PARTITIONS_DISCREPANCIES", "3")),
        "replication_factor": KAFKA_REPLICATION_FACTOR,
        "configs": {
            "retention.ms": "7776000000",  # 90 Days retention
            "cleanup.policy": "delete",
        },
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
