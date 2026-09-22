# Database Failure

> Operational response guide for **Runbooks / Database Failure**.

## Purpose

Use this runbook when runbooks / database failure is suspected or confirmed. The goal is to protect transaction integrity, maintain tenant isolation, communicate clearly, and restore normal processing with evidence.

## Scope and impact

This runbook covers the affected PesaGuard workflow, its dependencies, and customer-visible symptoms. Treat missing telemetry as an incident signal rather than assuming the system is healthy.

## First five minutes

1. Open an incident and record the UTC start time, affected tenant or provider account, correlation IDs, and current operator.
2. Check `/health`, application error rate, queue or Kafka lag, database connectivity, and recent deployment activity.
3. Confirm whether transaction ingestion is accepting, rejecting, duplicating, or delaying work.
4. Preserve audit and provider evidence before replaying, deleting, or mutating records.
5. Communicate a short status update with impact, mitigation, and next update time.

## Diagnosis

- Compare primary and replica health where read routing is enabled.
- Check structured logs by correlation ID; redact credentials and personal data.
- Inspect tenant-scoped dead letters, retry counts, outbox age, and idempotency records.
- Identify whether the failure is isolated to one tenant, provider account, region, or shared dependency.

## Mitigation

Prefer reversible controls: pause a failing consumer, disable a provider route, reduce concurrency, route reads to primary, or place malformed work in a dead-letter queue. Do not bypass authentication, tenant predicates, signatures, or idempotency checks to accelerate recovery.

## Recovery

1. Confirm the dependency is stable and the failure condition is understood.
2. Replay only tenant-scoped, validated records with an explicit operator and reason.
3. Verify counts, ordering, reconciliation outcomes, and duplicate protection.
4. Monitor retries, lag, error rates, and customer-facing latency for at least one recovery window.

## Escalation

Escalate to the service owner when data integrity is uncertain, more than one tenant is affected, recovery exceeds the service target, or a security control may have failed. Escalate to security for suspected credential exposure, cross-tenant access, spoofed callbacks, or unexplained privilege changes.

## Closure checklist

- [ ] Customer impact and affected scope are documented.
- [ ] All replayed or repaired records are auditable.
- [ ] Metrics returned to normal and alerts cleared.
- [ ] Backup and restore implications are reviewed.
- [ ] Follow-up owner, root cause, and due date are recorded.
