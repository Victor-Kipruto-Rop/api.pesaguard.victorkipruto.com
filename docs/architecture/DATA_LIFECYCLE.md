# Data Lifecycle

The lifecycle contract prevents a retention job or downstream consumer from silently skipping the evidence and ownership steps around financial data.

| Stage | Owner | Durable state | Access and validation | Failure behavior |
| --- | --- | --- | --- | --- |
| Created / Ingested | Webhook and API ingress | Request context, raw payload, idempotency intent | Authenticated tenant/provider scope and schema checks | Reject or persist to quarantine/DLQ; never acknowledge an unpersisted event |
| Validated | Data-quality and normalization boundary | Validation result, lineage, quality scores | Business rules, completeness, validity, consistency, and tenant checks | Quarantine with rule, hash, lineage, and replay context |
| Processed / Stored | PostgreSQL event store and domain services | Transaction, audit, reconciliation, and outbox rows | Database constraints, idempotency, state transitions, and atomic commits | Roll back and retry; preserve durable outbox intent |
| Consumed | Kafka/Redpanda consumer group | Broker event history and consumer offsets | Versioned schema, partition ordering, idempotent handlers | Retry with bounded backoff, then durable DLQ |
| Archived | Archive/object-storage boundary | Immutable tenant-partitioned archive object and manifest | Hash, encryption, retention policy, and legal-hold checks | Keep hot record and retry archival; do not delete source data |
| Deleted | Retention and deletion workflow | Deletion request, approval, audit evidence | Retention expiry, tenant scope, legal hold, and authorization | Abort deletion and alert; preserve evidence |

## Invariants

- Every state transition has one owning component and an observable result.
- `ARCHIVED -> DELETED` is required for lifecycle-managed records; quarantine is the explicit invalid-data branch.
- PostgreSQL owns current financial state; Kafka owns replayable delivery history; object storage owns archived raw evidence.
- Retention cleanup must be tenant-scoped, batched, legal-hold aware, and auditable.
- Access follows the authenticated tenant and least-privilege role at every stage.