# System Invariants

## Core invariants

PesaGuard is a correctness-first financial system. The architecture is designed around a set of invariants that must hold for every tenant, transaction, and reconciliation event.

### 1. Every financial event must be idempotent

A callback or retry must not create duplicate financial outcomes. Replaying the same event must resolve to the same durable state or a safe duplicate classification.

### 2. Every transaction must be scoped to a tenant and account

No financial record may be processed without an authorized tenant/A account context. Reads and writes must validate that scope before mutation or result exposure.

### 3. Durable state precedes side effects

The system must record the event and idempotency state before notifying downstream systems or making a business decision that claims success.

### 4. Reconciliation results must be explainable

Matching decisions must be traceable to a reason set, a score, and an auditable chain of records. Operators must be able to understand why a transaction was classified as matched, partial, duplicate, or unmatched.

### 5. Secret material must never enter the event trail

Provider credentials, bearer tokens, raw API keys, and sensitive payload values must be filtered before logs, events, and audit records are stored.

### 6. Failed operations must be recoverable

There is no silent drop of a callback or business transaction. Exceptions, retries, and dead-letter paths must leave enough evidence for replay.

### 7. Time and ordering matter

M-Pesa events and internal settlements can arrive out of order. The system must treat time windows, event sequence, and source-of-truth ordering as first-class concerns.

### 8. Safety must win over convenience

When there is ambiguity, the platform should reject, quarantine, or escalate rather than guess a financial state.

## Operational invariants

- Every alert must have an owner and actionable recovery path.
- Every critical dependency must have a health check and a recovery plan.
- Every migration must be reversible or safely backfilled.
- Every externally processed payload must be mapped to a correlation ID and tenant context.

## Why these invariants matter

These controls are what make PesaGuard suitable for a financial workflow. Without them, reconciliation becomes guesswork, and financial operations become difficult to audit when a dispute or incident occurs.
