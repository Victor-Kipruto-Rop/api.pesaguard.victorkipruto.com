# Core Data Engineering

## Purpose

PesaGuard is a financial data platform, not only an API application. Its data engineering responsibilities are to ingest trusted payment events, normalize them into a usable canonical model, reconcile them against internal records, preserve evidence, and ensure the system can be audited and replayed safely.

The platform must treat data quality, lineage, retention, and tenant isolation as production requirements because they directly affect financial correctness.

## 1. Data ingestion

PesaGuard ingests data from several sources, each with different reliability and contract expectations:

- M-Pesa Daraja webhook callbacks
- internal application APIs and admin operations
- background worker events and queue-dispatched messages
- reconciliation and anomaly detection outputs
- operational telemetry and audit records

The architecture expects ingestion to be durable before any downstream business action is treated as complete. This is enforced through the event store and idempotency ledger created in `models.py` and supporting modules.

## 2. Batch ingestion

Batch ingestion is used for larger or delayed data loads that are not required to complete in the request path. Typical use cases include:

- backfills for historical M-Pesa records
- bulk settlement or ledger snapshot imports
- reprocessing of stale or partially failed transactions
- reconciliation certification and testing data refreshes

Batch ingestion should remain explicitly versioned, auditable, and scoped to a single tenant and provider account. The system should never silently merge batch rows into the master transaction store without source traceability and validation.

## 3. Real-time ingestion

Real-time ingestion is the primary path for payment-event intake. A provider callback enters the system through the Flask webhook boundary, is validated, normalized, and then persisted before downstream reconciliation occurs.

This is consistent with the runtime behavior in `app.py`, which adds correlation metadata, validates the request, and uses idempotency and rate limiting before the event is accepted as a business record.

## 4. API ingestion

API ingestion covers all internal system actions that create or mutate data through explicit APIs. These endpoints are subject to auth, tenant scoping, and payload validation before they are stored.

Examples in the codebase include:
- tenant settings endpoints
- admin configuration operations
- webhook-driven ingestion routes
- internal reconciliation APIs and operational status calls

All API-created data should retain metadata about source, actor, tenant, and timestamp. A successful mutation must not be treated as durable until the corresponding write is committed.

## 5. Event ingestion

The system uses event ingestion for asynchronous, replay-safe processing. Events are captured from provider callbacks and internal workflows and dispatched through the queue or Kafka path.

This aligns with the event-driven architecture in `producer.py`, `event_store.py`, `background_tasks.py`, and the event models declared in `models.py`.

Event rules:
- event payloads must be validated before dispatch
- event ingestion must preserve correlation IDs and tenant scope
- event processing must be idempotent and replay-safe
- failures must be stored in a dead-letter or retry workflow instead of being silently discarded

## 6. Source connectors

Source connectors are the boundaries between external systems and PesaGuard’s canonical model. They are responsible for translating raw, provider-specific payloads into trusted internal records.

For the current product scope, the critical connector is the Safaricom Daraja M-Pesa connector, with additional connectors for internal operational data and outbound notification systems.

Connector responsibilities:
- verify the source and transport identity
- parse provider-specific structures
- convert fields into standard internal names
- reject malformed or invalid payloads
- attach a source reference and apply tenant context

## 7. Canonical data model

The canonical model is the common internal representation used after provider data is normalized. It is more stable than the raw upstream format and is designed to support reconciliation, analytics, and auditing.

The repository’s core persistence model reflects this intent:
- `Transaction` stores the durable transaction event and core business facts
- `IdempotencyRecord` prevents duplicate processing and replay issues
- `AuditEvent` records append-only operational evidence
- `TransactionEvent` tracks lifecycle and state transitions
- `ReconciliationMatch` stores the evidence for a decision outcome

Canonical concepts should include:
- tenant_id
- provider_account_id
- provider and source
- transaction_id / external_reference
- amount, currency, timestamp
- state and status
- correlation_id and created_at
- source payload hash or evidence pointer

## 8. Data normalization

Normalization translates diverse upstream shapes into a single internal contract. For M-Pesa, this includes standardizing fields such as transaction ID, amount, timestamp, phone number, and reference fields.

Normalization must:
- map raw field names into canonical names
- coerce types and decimal amounts into safe internal representations
- normalize timestamps to a consistent timezone-aware format
- lower or standardize status values and transaction types
- preserve the raw payload for forensic replay and audit

The reconciliation engine in `reconciliation_engine.py` is a concrete example of normalization and comparison logic applied to raw Daraja events and internal records.

## 9. Data transformation

Transformation applies business logic to raw or normalized data. It turns a generic event into an operational fact such as:

- transaction accepted
- transaction matched
- transaction duplicated
- transaction mismatched
- transaction flagged for investigation

Transformations should be explicit, versioned, and testable. They should also be isolated from the ingestion boundary so the raw payload and canonical model can evolve independently.

## 10. ETL/ELT

PesaGuard should favor an ELT-oriented pattern for the payment domain because it keeps the raw event trail intact, supports replay, and makes correction easier.

Recommended pattern:

1. ingest raw data into durable storage
2. validate and normalize it into a canonical representation
3. enrich and reconcile it in-place or in downstream work tables
4. expose analytical views or curated tables for ops and reporting

This approach fits the current architecture, where the source system retains raw payloads and downstream processes classify and reconcile based on them.

## 11. Data enrichment

Data enrichment adds operational and business context that is valuable for reconciliation, investigation, and support workflows.

Examples include:
- tenant metadata
- provider account configuration
- branch or merchant identifiers
- locale or residency context
- alert severity and escalation ownership
- internal ledger references
- risk, fraud, and anomaly flags

Enrichment must preserve provenance. Enriched fields should not obscure the origin of the raw event, and they must remain scoped to the tenant and account responsible for them.

## 12. Data aggregation

Aggregation is used to answer operational questions across transaction volumes:

- total transaction volume per tenant or provider account
- mismatch count by hour or day
- duplicate callback rate
- alert severity counts
- reconciliation success rate by provider and time period

Aggregations should be computed from the canonical dataset rather than from raw provider webhook payloads to keep the logic consistent and auditable.

## 13. Data partitioning

Data partitioning is necessary for scale, retirement, and operational isolation. The platform should partition by tenant, event time, or source domain where appropriate.

Recommended patterns:
- tenant-scoped tables or partitions where possible
- time-based partitions for high-volume transaction history
- operational partitioning between raw events, reconciled transactions, and audit records

Partitioning is not just a performance optimization; it is a governance mechanism that reduces accidental cross-tenant data exposure.

## 14. Data archival

Archival is the long-term move of older data that is no longer active but must retain legal, operational, or forensic value. PesaGuard should separate active transactional data from archival data based on business retention rules.

Archival must preserve:
- tenant boundaries
- original event payloads and hashes
- classification and reconciliation results
- audit and security evidence

Archived records should be read-only from operational workflows to avoid accidental mutation.

## 15. Data retention

Retention policies are defined by legal, operational, and contractual requirements. At minimum, the platform should support:

- hot storage for recent transaction and reconciliation activity
- warm storage for recent anomaly and audit evidence
- cold storage or archive for historical records
- tenant-specific retention schedules where required

Retention must be explicit and enforceable. It should not depend on ad hoc manual deletion operations.

## 16. Data deletion

Deletion is part of the data lifecycle and must be deliberate and policy-aware. The system should never allow blanket deletion of financial events without either:

- a documented retention schedule,
- a legal or operational authorization process,
- an auditable reason and timestamp

In practice, deletion should typically be a soft-delete or archival action before a hard purge is allowed. This preserves evidence and prevents irreversible mistakes.

## 17. Data lineage

Data lineage records how a raw payment event moved through the system. It answers questions like:

- where did this transaction originate?
- which connector received it?
- which normalization rules were applied?
- which reconciliation engine produced the result?
- which downstream alert or report used it?

The repository includes the right building blocks for lineage: raw transaction records, transaction lifecycle events, reconciliation evidence, and audit records. These should be connected by correlation IDs, event keys, and tenant-scoped identifiers.

## 18. Data catalog

The data catalog is the inventory of data assets and their semantics. It should describe:

- source tables and event streams
- ownership and stewardship
- data quality expectations
- schema versioning and freshness
- access and security classification
- business definitions for key fields

The catalog is essential because financial data assets are governed by tenant context, compliance, and operational obligations, not just technical convenience.

## 19. Data dictionary

The data dictionary is the reference documentation for each key field and entity. It defines the meaning, type, constraints, ownership, and usage of each data element.

Example core fields for PesaGuard:

| Field | Meaning | Type | Constraints | Ownership |
|---|---|---|---|---|
| tenant_id | Tenant or account owner | string | required, non-empty | platform admin |
| provider_account_id | Connected provider account for the tenant | string | required | platform admin |
| trans_id | M-Pesa unique transaction id | string | required | provider connector |
| trans_amount | Amount for the transaction | decimal | > 0 | reconciliation |
| currency | ISO currency code | string | 3-letter uppercase | data model |
| status | Transaction lifecycle state | string | restricted enum | reconciliation |
| correlation_id | End-to-end request/event trace | string | optional but recommended | platform observability |
| idempotency_key | Deduplication key | string | required, unique per scope | ingestion |
| match_score | Reconciliation confidence score | decimal | 0-1 | reconciliation |

The data dictionary should remain aligned with the database schema in `models.py` and the reconciliation semantics in `reconciliation_engine.py`.

## 20. Data governance expectations

To operate safely, PesaGuard must enforce the following data-governance practices:

- tenant isolation on all reads, writes, and exports
- schema evolution through migrations and explicit versioning
- append-only audit evidence for material changes
- clear field-level ownership and stewardship
- retention and deletion policies tied to business and legal requirements
- lineage and catalog metadata for every critical dataset

## 21. Implementation direction

The current repository already provides the building blocks for a disciplined data platform:

- `app.py` handles ingestion and request lifecycle
- `models.py` contains the dominant canonical entities and audit patterns
- `event_store.py` captures raw event evidence
- `reconciliation_engine.py` performs canonical reasoning and classification
- `producer.py` handles event dispatch and queue behavior
- `logging_utils.py`, `metrics.py`, and `health.py` support observability and evidence capture

The platform should continue to evolve by strengthening the canonical schema, lineage metadata, retention policies, and operational documentation around those core patterns.
