# Trust Boundaries

## Purpose

This document defines where the platform accepts untrusted input, where its sensitive state lives, and which boundaries need validation, isolation, and evidence.

## Trust boundaries in PesaGuard

### 1. Public internet and provider boundary

The external boundary includes:
- Safaricom Daraja callbacks
- customer-facing API traffic
- admin or operator sessions
- public tenant settings or operational endpoints

These inputs are untrusted until validated. The platform must verify provider identity, schema, tenant scope, and integrity before accepting the payload as authoritative business data.

### 2. API and web ingress boundary

The Flask web layer is the first internal trust boundary. It is responsible for:
- request validation
- rate limiting
- payload-size checks
- correlation ID attachment
- tenant/account association

Anything that reaches business logic after this layer is assumed to be internally valid, but still must be checked against tenant and account policies.

### 3. Business domain boundary

Inside the operator logic, sensitive decisions are made about:
- duplicate detection
- financial matching
- anomaly classification
- alert generation

This boundary requires invariants and explicit guardrails. Domain logic never assumes that any external payload is safe to use without normalization and policy checks.

### 4. Persistence boundary

The durable data store is a privileged boundary. Postgres and event tables contain:
- transaction events
- tenant identities
- operational metadata
- audit history
- dead-letter and retry state

The persistence layer must enforce record integrity and access controls. It is not a place for raw secrets or unredacted provider payloads.

### 5. Queue and worker boundary

Kafka, Redis, and worker jobs are asynchronous trust boundaries. Messages are treated as replayable events and must be safe to reprocess. Queued jobs cannot assume the original caller is still present; they must be able to validate the event, tenant information, and idempotency state.

### 6. Admin and operations boundary

Admin endpoints, configuration updates, and operator actions are privileged and must remain isolated from the public transaction pipeline. They require explicit validation and separate permission models.

## Required controls

- validate callback signatures for provider-originated traffic
- scope all tenant queries by authorized context
- redact or mask secrets in logs and telemetry
- avoid trusting downstream IDs without tenant/account checks
- require idempotent processing for all financial events

## Security consequence

The system must treat each trust boundary as a place where the platform can fail closed. When validation fails, the system should reject, quarantine, or dead-letter the event rather than guessing at intent.
