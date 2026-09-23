# State Ownership

PesaGuard uses several infrastructure systems, but they do not have equal authority. A component may cache, transport, or coordinate state without owning the financial truth.

## Ownership matrix

| State | Authoritative owner | Other systems may hold | Recovery rule |
| --- | --- | --- | --- |
| Transactions, idempotency records, reconciliation results, discrepancies, audit records, dead letters, and outbox status | PostgreSQL | Protected event payloads in the outbox and derived dashboards | Rebuild service state from PostgreSQL backups and migrations; replay unpublished outbox or dead-letter records |
| Raw provider files and batch-import objects | Object storage | Import-job metadata and processing counters in PostgreSQL | Recreate import work from the object key and PostgreSQL import-job record; object versions/retention must outlive processing retries |
| Published transaction and workflow events | Kafka/Redpanda | Consumer-local offsets and derived projections | Kafka is the replayable event transport/history, not the authority for current transaction state; retain events for the agreed replay window |
| RQ jobs and queue dispatch metadata | Redis/RQ | Durable intent in PostgreSQL outbox or import-job rows | Redis loss may delay work, but must not lose an accepted transaction; reschedule from durable PostgreSQL work records |
| Rate-limit counters, short-lived locks, cache entries, and consumer lag snapshots | Redis or process memory | Metrics and logs | These are disposable coordination or observability state; expiration or loss must not change financial outcomes |
| User sessions and revocation state | PostgreSQL session tables | Redis cache, when configured | Authentication must fail closed when the authoritative session/revocation store is unavailable |

## Rules

1. PostgreSQL owns the current financial state. A cache, queue, or event consumer must never be the only place an accepted transaction exists.
2. The webhook path commits the transaction, idempotency record, audit evidence, and downstream outbox intent before acknowledging success.
3. Kafka/Redpanda provides ordered, partitioned delivery and replay. Consumers must be idempotent because event delivery is at-least-once.
4. Redis/RQ coordinates work and absorbs bursts. It is not a ledger, inbox, or dead-letter authority.
5. Process-local sets, caches, and lag registries are advisory only. Restarting a worker must not cause data loss or duplicate financial effects.
6. Object storage owns immutable raw batch inputs; PostgreSQL owns the lifecycle and outcome of processing those inputs.

## Failure consequences

- **PostgreSQL unavailable:** reject or retry the inbound request; do not acknowledge it as accepted.
- **Redis unavailable:** retain the PostgreSQL outbox/import intent and retry scheduling; do not put the only copy of the payload in Redis.
- **Kafka unavailable:** leave the PostgreSQL outbox row retryable or dead-letter it after the bounded attempt policy.
- **Object storage unavailable:** leave the import job queued or failed with an actionable error; do not mark records processed.
- **Process restart:** reconstruct work from PostgreSQL, Kafka offsets/history, and object keys rather than in-memory state.

## Review test

For every new stateful feature, identify its authoritative owner, its recovery source, its retention policy, and the behavior when that owner is unavailable. If the answer is “an in-memory variable,” the design is not durable enough for financial processing.