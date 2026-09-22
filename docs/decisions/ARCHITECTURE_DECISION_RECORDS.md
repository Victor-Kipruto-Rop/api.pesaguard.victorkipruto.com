# Architecture Decision Records

This directory captures the decisions that shape how PesaGuard is designed and operated. Each ADR records a specific architectural choice, the tradeoffs considered, and the conditions under which the decision should be revisited.

## Current ADR set

- [ADR-001: Modular Monolith](ADR-001-MODULAR-MONOLITH.md) — keep a single cohesive codebase with explicit domain boundaries for now.
- [ADR-002: PostgreSQL as the system of record](ADR-002-POSTGRESQL.md) — use PostgreSQL for durable financial and operational records.
- [ADR-003: Kafka for event transport](ADR-003-KAFKA.md) — use Kafka for async event dispatch and fan-out.
- [ADR-004: Redis for cache and queue coordination](ADR-004-REDIS.md) — use Redis for rate limiting, caching, and worker coordination.
- [ADR-005: Provider adapters for payment rails](ADR-005-PROVIDER-ADAPTERS.md) — isolate provider-specific logic behind a normalized event contract.
- [ADR-006: Multi-tenant isolation architecture](ADR-006-MULTI-TENANCY.md) — enforce tenant scoping across storage, APIs, and event processing.
- [ADR-007: AWS-oriented deployment model](ADR-007-AWS-ARCHITECTURE.md) — define the intended deployment pattern and platform assumptions.

## Decision review expectations

When a practical change affects a product requirement, data model, security boundary, or provider integration, the team should:

1. identify the affected ADR,
2. assess whether the decision still holds,
3. document new context and tradeoffs,
4. update the ADR or add a new record if the decision materially changes.

## ADR lifecycle

- Proposed — under discussion or not yet approved
- Accepted — in effect for current operations
- Superseded — replaced by a newer decision
- Deprecated — retained for historical record only

The platform should treat financial correctness and tenancy guarantees as the highest-priority decision criteria when reviewing these records.
