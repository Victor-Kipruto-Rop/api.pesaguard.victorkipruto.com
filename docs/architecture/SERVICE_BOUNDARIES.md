# Service Boundaries

## Purpose

This document defines the service ownership model in PesaGuard. The system is intentionally organized as a modular monolith so the application can remain deployable and operationally straightforward without losing boundaries between transaction intake, policy, reconciliation, async work, and observability.

## Boundary model

### 1. Web and API boundary

Responsible for:
- receiving M-Pesa callbacks and internal API traffic
- validating request structure and transport concerns
- attaching tracing and correlation metadata
- checking tenant context and authorization

Owned by Flask route modules and request middleware around the `pesaguard_backend_pipeline` package.

### 2. Validation and normalization boundary

Responsible for:
- translating provider payloads into internal event contracts
- rejecting malformed or duplicate payloads early
- enforcing payload size limits and source checks

This boundary isolates provider-specific differences from business logic.

### 3. Event store and idempotency boundary

Responsible for:
- persisting raw and normalized events
- enforcing idempotency and dedupe logic
- recording durable audit and replay state

This is the system’s source of truth for webhook evidence and downstream replay safety.

### 4. Reconciliation and anomaly domain

Responsible for:
- matching provider events to internal records
- scoring confidence and classifying outcomes
- identifying mismatches, reversals, duplicates, and exceptions

This boundary is where business correctness is judged and should remain comparatively isolated from external client concerns.

### 5. Async workflow boundary

Responsible for:
- background job execution
- queue-based event flow
- delayed alerts and notification dispatch
- retry and dead-letter recovery paths

This boundary is intentionally asynchronous so user-facing processing does not block on long-running tasks.

### 6. Policy and tenant governance boundary

Responsible for:
- authorization and role checks
- tenant configuration and user overrides
- allowed-source, rate-limit, and residency policy enforcement

Sensitive configuration must not be mixed with operational transaction processing.

### 7. Observability boundary

Responsible for:
- logs, metrics, traces, health checks, and operator evidence
- incident correlation and operational analysis

Observability is treated as a cross-cutting boundary, not an optional add-on.

## Interface rules

- The web boundary must not perform deep business reconciliation decisions.
- The domain boundary must never depend on raw provider payloads directly.
- The queue boundary must receive only already-validated, tenant-scoped events.
- The notification boundary must not create or mutate financial state.
- The persistence boundary must be the last to acknowledge completion of a transaction step.

## Ownership expectations

Each component should have a clear owner in code review and operations. If a service depends on another service, the dependency must be explicit, versioned at the contract boundary, and observable under failure.

## Operating principle

The platform should prefer clear ownership over clever coupling. If a task can be delayed or isolated, it should move to an async boundary rather than be embedded in the request thread.
