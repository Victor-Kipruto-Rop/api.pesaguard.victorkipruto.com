# Dependency Map

## Runtime dependency model

PesaGuard depends on a small set of critical runtime services and provider integrations. The design keeps business logic local while making the platform operationally observable and recoverable.

## Internal dependencies

### Application runtime
- `Flask` web server for webhook and admin endpoints
- `SQLAlchemy` models and session handling for durable persistence
- `Redis` for rate limiting, caching, and queue coordination
- `Kafka` for event dispatch and asynchronous fan-out
- `RQ`/worker style background processors for non-blocking jobs
- `Alembic` for schema migration and safe evolution

### Business domain modules
- `app.py` and route modules provide ingress and public contracts
- `event_store.py` owns durable event storage and replay logic
- `reconciliation_engine.py` performs raw-to-ledger comparison
- `alerting_service.py` and `notifier.py` deliver operational notifications
- `tenant_settings.py` and `auth_rbac.py` enforce environment and tenancy policy
- `metrics.py` and `health.py` provide observability interfaces

## External dependencies

### Payment provider dependency
- Safaricom Daraja / M-Pesa webhook callbacks
- callback payload structure and signature behavior are treated as an external contract
- payload normalization is required before business logic is allowed to use the data

### Communications dependency
- Africa's Talking or equivalent notifier integration
- used only for operational messaging and escalation, not for ledger settlement

### Infrastructure dependency
- PostgreSQL for durable transaction and audit storage
- Redis for short-lived rate limits and queue coordination
- Kafka for event streams and asynchronous work distribution
- backing services are treated as operational dependencies, not business logic

## Dependency rules

1. Domain services do not call external providers directly unless the integration boundary is explicitly wrapped.
2. All business logic depends on a normalized internal event model, not raw provider objects.
3. Downstream consumers must be able to operate safely if a notifier or Kafka broker is briefly unavailable.
4. Tenancy and account context must be attached before business processing begins.
5. Secret material must never be embedded in event records or logs.

## Failure handling expectations

- If Kafka is unavailable, the system should retain the event locally and retry or dead-letter it without losing the original business record.
- If Redis is unavailable, the user-facing request may fail gracefully if rate limiting or cache state is required for the path.
- If PostgreSQL becomes unavailable, the system must stop before asserting successful processing.
- External provider retries must be idempotent and safe to re-run.

## Dependency map summary

Application code
  -> PostgreSQL / Redis / Kafka / provider APIs

Business logic
  -> validated event model + tenant context + durable store

Notification and audit
  -> event store + policy + external comms service

Operations
  -> health, logs, metrics, traces, backups, and incident runbooks
