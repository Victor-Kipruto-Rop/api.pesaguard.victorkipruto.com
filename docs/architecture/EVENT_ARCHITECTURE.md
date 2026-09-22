# Event Architecture

## Overview

PesaGuard uses an event-first model even though the application is still structured as a modular monolith. Events represent normalized facts about provider callbacks, reconciliation outcomes, and downstream operator actions.

## Event model

The platform follows a consistent pattern:
- an inbound transaction callback becomes a durable event record
- normalized event data is routed through an idempotent pipeline
- downstream business actions are triggered by the event, not by direct ad hoc calls
- every event carries enough metadata to replay, audit, and explain the outcome

## Event flow

```text
M-Pesa callback
  -> normalized provider event
  -> event store + idempotency check
  -> Kafka or queue dispatch
  -> reconciliation worker
  -> discrepancy / alert producer
  -> notification or reporting consumer
  -> audit trail and observability
```

## Event types

Although not every event type is finalized in code today, the platform is designed around a common taxonomy:

- `transaction.received`: provider callback captured at ingress
- `transaction.normalized`: provider payload converted to internal event model
- `transaction.idempotent`: duplicate or replay state confirmed
- `transaction.reconciled`: business match classification produced
- `transaction.alerted`: mismatch, anomaly, or suspicious event flagged
- `notification.sent`: operator-facing action dispatched
- `audit.recorded`: compliance or operational evidence persisted

## Producer and consumer responsibilities

### Producers
- webhook ingress captures the provider event
- business services create reconciliation or alert events
- queue and Kafka producers emit validated events to downstream consumers

### Consumers
- async worker processes handle reconciliation or alerting tasks
- notification workers publish messages to email or messaging providers
- operational observers consume health and metrics events for monitoring

## Event quality rules

- event payloads must be validated before enqueueing
- event processing must be idempotent and replay-safe
- event versioning should be explicit when contracts evolve
- event records must not contain raw secret material
- every event must carry correlation metadata and tenant context

## Why this matters

In a financial workflow, the system must be able to answer: what happened, when, why, and under which tenant context? Event architecture provides that traceability without overengineering the platform into a distributed system prematurely.
