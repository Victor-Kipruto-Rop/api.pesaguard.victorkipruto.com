# PesaGuard Data Platform Architecture

## Purpose

PesaGuard is one tenant-scoped financial data platform. Provider connectors,
file imports, reconciliation, fraud assessment, reporting, and operational
APIs are different paths through the same governed data lifecycle; they are not
independent feature silos.

## Platform flow

```text
M-Pesa / Airtel / banks / POS / files / external APIs
                         |
                         v
                 [Connector ingestion]
                         |
                         v
                 [Queue or Redpanda]
                         |
                         v
                    [Raw evidence]
                         |
                         v
              [Validation + schema contract]
                         |
                         v
                [Canonical transaction model]
                         |
                         v
                 [Normalize + transform]
                    /              \
                   v                v
          [PostgreSQL operational] [Data lake/archive]
                   \                /
                    v              v
              [Enrichment + aggregation]
                         |
                         v
                [Reconciliation + fraud]
                    /       |        \
                   v        v         v
                 [API] [Dashboard] [Reports]

Cross-cutting: lineage | catalog | quality | audit | monitoring | security
```

The current deployment may run these stages in a modular monolith with
PostgreSQL and a queue. Redpanda/Kafka and a lake are scale-out deployment
options, not separate domain models. The invariants remain the same in either
deployment shape.

## Stage contracts

### 1. Connector ingestion

Each connector translates one source protocol into an ingestion envelope. The
envelope must include `tenant_id`, `provider_account_id`, `source`, a stable
external reference, an observed timestamp, a correlation ID, a schema version,
and the original payload or an immutable evidence pointer.

Connectors authenticate the source, apply request-size and transport checks,
and do only source-level parsing. They must not write directly to reporting,
fraud, or reconciliation tables.

### 2. Queue and durable capture

The accepted envelope is durably captured before downstream work is claimed
complete. Publication uses an outbox or an equivalent transactional handoff.
Transient failures are retried with bounded backoff; exhausted messages are
dead-lettered with tenant, source, schema, and failure metadata. Duplicate
delivery is expected and safe.

### 3. Validation and canonicalization

Validation separates malformed input from valid business exceptions. A valid
envelope becomes the canonical transaction model with decimal monetary values,
an explicit ISO currency, normalized timezone-aware timestamps, source identity,
and tenant-scoped idempotency keys. Raw evidence remains immutable and linked
to the canonical record by a hash or evidence ID.

### 4. Operational and analytical storage

PostgreSQL is the operational source for tenant-scoped transaction state,
idempotency, reconciliation evidence, audit records, outbox state, and queryable
workflow status. A data lake or archive is the immutable, replay-oriented home
for high-volume raw evidence, historical snapshots, and analytical extracts.
Neither store bypasses retention, privacy, lineage, or tenant access controls.

### 5. Enrichment and decisioning

Enrichment adds provider-account, merchant, branch, ledger, risk, and ownership
context while preserving provenance. Aggregations are derived from canonical
records, not ad hoc webhook payloads. Reconciliation and fraud decisions are
versioned, explainable, replay-safe, and independently auditable.

### 6. Serving and reporting

APIs, dashboards, and scheduled reports read governed operational or curated
analytical views. They do not become alternate sources of financial truth.
Exports include tenant scope, data freshness, schema/version metadata, and the
decision or aggregation provenance needed for investigation.

## Cross-cutting controls

- **Tenant isolation:** tenant identity is derived from the authenticated
  principal or trusted connector configuration, never from an untrusted payload.
- **Idempotency:** uniqueness is scoped by tenant, provider account, provider,
  and external reference as appropriate for the source contract.
- **Lineage:** every canonical record can be traced to its source envelope,
  connector version, transformations, decisions, and published outputs.
- **Quality:** schema, completeness, referential, freshness, and reconciliation
  quality checks produce measurable outcomes and quarantine invalid data.
- **Audit:** security-sensitive and financial state changes are append-only and
  contain hashes or references rather than raw secrets.
- **Observability:** ingestion lag, queue depth, dead letters, duplicate rate,
  reconciliation latency, data-quality failures, and report freshness are
  first-class metrics.
- **Security and privacy:** payload minimization, encryption, access control,
  retention enforcement, and redaction apply across raw, operational, and
  analytical stores.

## Delivery sequence

1. Stabilize the provider-neutral ingestion envelope, outbox, dead-letter, and
   replay contracts around the existing M-Pesa path.
2. Add connectors for additional payment rails and files without changing the
   canonical transaction or reconciliation contracts.
3. Introduce lake/archive sinks and curated analytical views after replay,
   retention, and restore tests are measurable.
4. Scale queue, storage, and workers using production-shaped load tests with
   explicit SLO, RPO, and RTO acceptance criteria.

See [DATA_FLOW.md](DATA_FLOW.md), [SYSTEM_INVARIANTS.md](SYSTEM_INVARIANTS.md),
and [CORE_DATA_ENGINEERING.md](../database/CORE_DATA_ENGINEERING.md) for the
operational details and existing implementation boundaries.