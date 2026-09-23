# Feature Design Checklist

Use this checklist before implementing a PesaGuard feature and again during review. A feature is not complete because its happy-path function works; it is complete when its ownership, contracts, failure behavior, and operational lifecycle are explicit.

## Design

- [ ] **Subsystem:** Which boundary owns this feature: ingress, validation/data quality, event store, reconciliation, async workflow, notification, policy, or observability?
- [ ] **Input:** What data enters it? Define schema, source, tenant/provider scope, size limits, normalization, and trust level.
- [ ] **State:** What state does it own? Identify the authoritative store, retention period, encryption requirements, legal holds, and deletion path.
- [ ] **Contract:** What API, event, database, or worker contract does it expose? Define idempotency key, ordering, versioning, and compatibility behavior.
- [ ] **Security:** Who can access it? Derive tenant identity from the authenticated principal, enforce least privilege, and redact secrets from logs/events.

## Failure and scale

- [ ] **Failure:** What happens on malformed data, duplicate delivery, timeout, unavailable database, unavailable broker/cache, partial success, and corrupted payload?
- [ ] **Recovery path:** Is work retried with bounded backoff, quarantined, dead-lettered, replayable, or rolled back? What evidence remains?
- [ ] **Scale:** What are throughput, latency, concurrency, partitioning, batching, backpressure, connection-pool, and horizontal-scaling limits?
- [ ] **Lifecycle:** Which stages does the data pass through, who owns each stage, and what prevents premature archival or deletion?

## Verification and operations

- [ ] **Tests:** Cover the happy path, duplicate/replay path, invalid input, tenant isolation, partial failure, outage, migration compatibility, and recovery path.
- [ ] **Observability:** Emit structured logs, metrics, and traces for entered, succeeded, failed, retried, quarantined/DLQ, latency, backlog, and affected tenant without exposing payload secrets.
- [ ] **Deployment:** Define migration ordering, CI gates, image/build identity, health checks, smoke tests, rollout approval, and rollback trigger.
- [ ] **Recovery:** Define backup/restore implications, point-in-time recovery, replication, restore validation, RPO, RTO, and the drill command or runbook.

## Review exit gate

Do not approve the feature until every unchecked item is either implemented, covered by an explicit operational dependency, or recorded as a deliberate limitation with an owner and follow-up date.