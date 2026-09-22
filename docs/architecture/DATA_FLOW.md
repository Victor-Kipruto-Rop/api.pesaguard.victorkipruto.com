# Data Flow

## Overview

Data flow in PesaGuard follows a strict financial-processing pattern: trust a
source only after validation, persist evidence early, canonicalize once,
reconcile later, and serve all outputs from governed state. M-Pesa is the
current primary source, but the same flow applies to payment rails, files, and
external APIs.

## Normal data path

```text
Source connector
  -> ingestion envelope
  -> request/file validation and rate limiting
  -> tenant and provider-account resolution
  -> raw evidence capture
  -> schema validation and canonicalization
  -> idempotency and dedupe checks
  -> outbox / queue dispatch
  -> PostgreSQL and lake/archive sinks
  -> enrichment and aggregation
  -> reconciliation and fraud engines
  -> API / dashboard / report views
```

## Detailed flow

### Step 1: intake

An external event enters through its connector, such as the M-Pesa webhook
ingress in `app.py`. The source is checked for:
- source validity and allowed IP or provider constraints
- request size limits
- schema sanity and field completeness
- correlation ID and trace propagation

### Step 2: tenant and account scoping

The system resolves the tenant context before it allows any financial interpretation. This step is critical because provider callbacks are not globally trusted and must be associated with the correct account and tenant context.

### Step 3: normalization and validation

Raw M-Pesa fields are translated into PesaGuard’s internal representation. Examples include fields like `TransID`, `TransAmount`, `BillRefNumber`, and transaction type normalizations. The system must ensure that the data is internally consistent before it is treated as a business record.

### Step 4: idempotency and dedupe

Before any downstream effect, the system checks whether the event has already been consumed. This is the primary defense against duplicate callback delivery and replayed webhook retries.

### Step 5: durable event record

The raw and normalized event are stored in an append-only durable state. The system must not claim success based only on an in-memory result. Processing only becomes durable when the event and idempotency record are safely committed.

### Step 6: async dispatch

Once persisted, the event can be published to Kafka or dispatched through queue workers for non-blocking processing. This keeps the webhook path responsive while still supporting downstream reconciliation and notification flows.

### Step 7: reconciliation decision

The reconciliation engine compares the external event against internal records, using reference, amount, timestamp, and phone-based checks. Each result is assigned a classification such as `MATCHED`, `PARTIAL`, `MISMATCH`, `DUPLICATE`, or `UNMATCHED`.

### Step 8: alert and notification

For a mismatch or suspicious pattern, the system creates a business event that can trigger notifications, escalation, or remediation workflows. Notifications are not the financial source of truth; they are operational outputs of the reconciled state.

## Data guarantees

- provider payloads are normalized before being used in business logic
- financial side effects are only attempted after persistence
- every record keeps enough metadata for forensics and replay
- audit entries are append-only and do not contain secrets

## Storage concerns

The durable store holds:
- incoming provider events
- normalized transaction state
- reconciliation decisions
- audit trail and processing evidence
- dead-letter and retry records

This ensures the platform can explain what happened, even when a downstream component fails.
