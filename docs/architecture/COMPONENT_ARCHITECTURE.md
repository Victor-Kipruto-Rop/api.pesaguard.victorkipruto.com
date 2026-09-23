# Component Architecture

## Overview

PesaGuard is implemented as a modular monolith with explicit boundaries around ingestion, validation, storage, reconciliation, alerting, and operations. The application remains a single deployable runtime, but the codebase is intentionally organized so each component owns one responsibility and has a documented interface.

State ownership and recovery responsibilities are defined in [State Ownership](STATE_OWNERSHIP.md). PostgreSQL owns current financial state; Redis/RQ coordinates disposable work; Kafka provides replayable transport; and object storage owns immutable raw batch inputs.

## Primary components

### 1. Ingress and API boundary

Owned by the Flask application entrypoints in the `pesaguard_backend_pipeline` package, especially `app.py` and related route modules.

Responsibilities:
- accept M-Pesa Daraja callbacks and other authenticated calls
- apply transport-level safeguards such as request size limits, IP checks, and rate limiting
- attach correlation IDs and tracing metadata
- reject malformed or unauthorized traffic early

Key runtime concerns:
- webhook signature verification
- tenant and account resolution
- request context propagation
- safe error handling without leaking secrets

### 2. Event and state capture layer

Implemented by `event_store.py`, `idempotency.py`, and supporting persistence modules.

Responsibilities:
- receive raw provider payloads
- normalize field names and timestamps
- enforce idempotency keys and dedupe rules
- persist durable event records before downstream side effects are triggered

This layer is the source of truth for replay and forensic analysis.

### 3. Reconciliation and anomaly engine

Implemented by `reconciliation_engine.py`, `reconciliation_scoring.py`, and supporting utilities.

Responsibilities:
- compare external transaction events to internal ledger or operational records
- classify outcomes as `MATCHED`, `UNMATCHED`, `PARTIAL`, `MISMATCH`, or `DUPLICATE`
- score confidence and produce auditable decisions
- support alert generation for anomalous or delayed transactions

### 4. Workflow orchestration and background jobs

Implemented by `background_tasks.py`, `alerting_consumer.py`, `event_consumer.py`, and queue helpers.

Responsibilities:
- process asynchronous jobs without blocking the callback path
- drain outbox or event work after durable writes are committed
- fan out notifications, retries, and operational actions
- isolate expensive or time-consuming work from the request thread

### 5. Policy, security, and tenant governance

Implemented by `auth_rbac.py`, `rbac.py`, `security_helpers.py`, `tenant_settings.py`, and related modules.

Responsibilities:
- authenticate callers and validate permissions
- scope access to tenant and account boundaries
- enforce operational controls such as admin tokens and user-level settings
- manage data protection, retention, and local overrides

### 6. Notification and escalation layer

Implemented by `alerting_service.py`, `email_service.py`, `africas_talking.py`, and related notifier modules.

Responsibilities:
- send human-readable alerts for mismatches, failures, or fraud signals
- escalate based on configured severity and ownership
- deliver operator notifications without creating new financial side effects

### 7. Observability and operations

Implemented by `logging_utils.py`, `metrics.py`, `observability.py`, `health.py`, and tracing helpers.

Responsibilities:
- emit structured logs, metrics, and traces
- expose health and readiness signals
- correlate business events with technical failures
- support incident response and compliance review

## Interaction model

The component graph is:

External providers
  -> Webhook/API ingress
  -> Validation and authentication
  -> Event capture and idempotency
  -> Durable transaction/event store
  -> Reconciliation engine
  -> Alerting / notification / reporting
  -> Operational dashboards and audits

The system intentionally favors a write-then-async pattern:

1. Validate and normalize the inbound event.
2. Persist the event and idempotency record.
3. Publish or enqueue a downstream workflow.
4. Reconcile and notify asynchronously.
5. Record evidence for audit and replay.

## Design intent

This architecture keeps the system simple enough for a focused fintech team to operate while still enforcing financial-grade correctness. The modular monolith is a conscious tradeoff: easier operational overhead than a distributed system, without relaxing the transaction and tenant safety requirements.
