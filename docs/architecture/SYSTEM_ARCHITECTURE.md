# System Architecture

## 1. System purpose

PesaGuard is a real-time reconciliation and anomaly-detection system for M-Pesa-driven financial operations. It exists to help SACCOs, fintech operators, and merchant-facing businesses detect payment mismatches, duplicates, reversals, and suspicious activity before the business is exposed to financial loss or operational confusion.

The system is designed around one core value: a payment event is only useful if it is trustworthy, correctly reconciled, and explainable to operations teams.

## 2. System boundary

### In scope
- M-Pesa callback ingestion
- transaction normalization and validation
- idempotency and duplicate detection
- internal reconciliation against ledger or operational records
- anomaly and discrepancy classification
- alerting, auditing, and operational telemetry
- tenant-aware configuration and access control

### Out of scope
- core ledger settlement processing outside the reconciliation domain
- general-purpose accounting or ERP features beyond payment tracking
- becoming a general-purpose data warehouse or lakehouse for unrelated domains
- untrusted or unsanctioned admin bypasses
- storing raw secret material in event payloads or logs

## 3. Users and actors

### Primary users
- Finance and reconciliation officers
- branch or operations managers
- compliance and audit reviewers
- support teams investigating failed or suspicious payments

### Platform actors
- Safaricom Daraja / M-Pesa as the upstream provider
- internal Flask services handling webhook intake
- background workers processing async events and alerts
- administrators managing tenant configuration and access policies
- observability and operations tooling for telemetry, health, and incident response

## 4. System responsibilities

The platform is responsible for:
- receiving and validating payment events
- preserving evidence of each transaction as a durable event
- preventing duplicate processing by idempotency enforcement
- reconciling external events to internal records
- classifying mismatches, partial matches, duplicates, and exceptions
- generating alert and escalation workflows
- exposing auditable health and reconciliation state
- enforcing tenant and auth boundaries across APIs and data access

## 5. Non-responsibilities

PesaGuard is not:
- the source-of-truth ledger for all accounting records
- an enterprise ERP replacement
- a generic message bus for unrelated business domains
- a place for storing raw API tokens, credentials, or secret material
- responsible for automatically settling disputed amounts without operator review

## 6. Architecture overview

PesaGuard is a provider-neutral data platform with a modular-monolith runtime.
M-Pesa is the current primary connector, while the ingestion contract is
designed to admit additional rails, files, and external APIs without creating
parallel transaction models. The complete stage contract is documented in
[DATA_PLATFORM_ARCHITECTURE.md](DATA_PLATFORM_ARCHITECTURE.md).

The repository implements a modular monolith, not a distributed microservice grid. This keeps deployment and operational complexity manageable while maintaining service boundaries and event-driven workflows.

```text
External provider / file / API
        |
        v
[Connector ingestion]
        |
        v
[Queue or outbox]
        |
        v
[Raw evidence + validation + canonical model]
        |
        +----> [PostgreSQL + lake/archive]
        |                 |
        |                 +----> [Enrichment + aggregation]
        |                                   |
        |                                   v
        +----> [Reconciliation + fraud engine]
        |                 |
        |                 +----> Results + Audit
        |
        +----> [Background Workers]
                          |
                          +----> Alerts / Notifications / Escalation
                          |
                          +----> Observability + Health + Monitoring
```

## 7. Component architecture

The runtime structure is organized around the following layers:

- API and webhook ingress: Flask routes and request validation
- domain processing: reconciliation, anomaly handling, and workflow decisions
- persistence: PostgreSQL-backed record storage and event history
- messaging: Kafka and Redis-based async delivery and queue coordination
- notifications: alerting and escalation integrations
- operations: metrics, traces, health checks, and audit trail support

See [COMPONENT_ARCHITECTURE.md](COMPONENT_ARCHITECTURE.md) for the detailed component map.

## 8. Service boundaries

The codebase intentionally separates:
- ingress and request handling
- event recording and idempotency
- reconciliation logic
- notification logic
- policy and RBAC
- observability and operational monitoring

This separation prevents the request path from becoming entangled with asynchronous business work and keeps financial logic easier to reason about under load.

## 9. Trust boundaries

The platform treats the following as trust boundaries:

- public internet and provider callbacks
- API request validation layer
- tenant and account authorization layer
- persistence and event store
- queue and worker processing boundary
- admin and operational configuration surface

See [TRUST_BOUNDARIES.md](TRUST_BOUNDARIES.md).

## 10. System invariants

PesaGuard relies on a small set of invariants that must hold in all deployments:
- every financial event is idempotent
- every transaction is scoped to a tenant and account
- durable state is written before downstream action is claimed complete
- reconciliation decisions must be explainable and auditable
- secret material must never be stored in raw logs or event records

See [SYSTEM_INVARIANTS.md](SYSTEM_INVARIANTS.md).

## 11. Engineering principles

The implementation follows a correctness-first model:
- correctness over speed
- evidence over guesswork
- idempotency by default
- tenant isolation by design
- safe failure and replayability

See [ENGINEERING_PRINCIPLES.md](ENGINEERING_PRINCIPLES.md).

## 12. Outcome

PesaGuard is designed to be operationally simple enough for a focused fintech team to run, but strict enough to behave like a trust-sensitive financial platform. The current architecture is a modular monolith with explicit service boundaries and an event-driven execution model when asynchronous work is required.
