# Redis

> Decision record for **Decisions / Adr 004 Redis**.

## Status

**Proposed.** Confirm the decision against the deployed system and record an approval date before treating it as binding.

## Context

PesaGuard is a tenant-isolated financial reconciliation platform. This decision affects an explicit architectural decision, its context, tradeoffs, and consequences. The decision must preserve clear ownership, predictable failure behavior, auditability, and a migration path that does not interrupt transaction ingestion.

## Decision

Adopt the smallest approach that fits the current Flask, SQLAlchemy, PostgreSQL, Redis, Kafka, RQ, and Alembic architecture. Keep the boundary explicit, make tenant and account scope part of the contract, and prefer reversible rollout steps.

## Alternatives considered

1. **Existing repository pattern:** lowest migration risk and easiest operational adoption.
2. **A new standalone service:** stronger isolation, but higher deployment, observability, and data-consistency cost.
3. **A shared implicit convention:** fastest initially, but weak against drift, partial failures, and security regressions.

## Consequences

### Positive

- Ownership and failure behavior are visible to maintainers.
- Security and operational controls can be tested at the boundary.
- Future extraction remains possible because the contract is documented first.

### Tradeoffs

- The boundary adds review and migration work.
- Existing callers may need compatibility adapters during rollout.
- Metrics, audit records, and runbooks must evolve with the implementation.

## Implementation guardrails

- Use Alembic for schema changes; never introduce production `create_all()` behavior.
- Scope reads and writes by tenant and provider account where applicable.
- Never log credentials, bearer tokens, raw API keys, or sensitive payloads.
- Add focused tests before changing shared behavior.

## Validation

Validate imports, migration heads, focused tests, failure paths, and the relevant Docker or service configuration. Record the exact command and result in the change that implements this decision.

## Open questions

- Which team owns the boundary in production?
- What SLO and recovery target apply?
- Which compatibility period is required for existing clients?
