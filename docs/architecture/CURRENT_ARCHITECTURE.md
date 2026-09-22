# PesaGuard Current Architecture

## 1. Existing Architecture

PesaGuard is a Flask and SQLAlchemy backend deployed as separate processes: an M-Pesa webhook receiver, dashboard API, Kafka reconciliation consumer, and RQ worker. The active product scope is M-Pesa/Daraja reconciliation and anomaly detection.

## 2. Existing Communication Functionality

- Africa's Talking SMS client: `pesaguard_backend_pipeline/africas_talking.py`
- Slack webhook alerts and SMTP email alerts: `pesaguard_backend_pipeline/notifier.py`
- Localized alert templates: `alerting/templates/`
- Escalation and on-call services: `escalation_engine.py`, `on_call_service.py`
- Existing outbound webhook delivery manager: `webhook_manager.py`

The current alerting path calls providers directly and does not yet provide a provider-neutral notification lifecycle, delivery report model, inbound Africa's Talking webhook processing, or communication analytics.

## 3. Existing Integrations

- Active: Safaricom Daraja/M-Pesa callbacks, OAuth, validation, idempotency, reconciliation, and anomaly rules.
- Generic provider configuration and encrypted credentials exist in `provider_management_service.py`.
- Airtel Money, bank transaction adapters, Africa's Talking USSD, voice, WhatsApp, airtime, and data integrations are not implemented.

## 4. Event Infrastructure

- Kafka (`kafka-python-ng`) carries M-Pesa raw, matched, discrepancy, dead-letter, and audit topics.
- Redis carries RQ jobs, rate limits, and short-lived/cache state.
- RQ workers handle asynchronous transaction publishing, scheduled reports, cleanup, and failures.
- Communication topics and communication-specific workers are not yet defined.

## 5. Database Structure

Production uses PostgreSQL; tests and local paths also use SQLite. SQLAlchemy models are in `pesaguard_backend_pipeline/models.py` and audit models in `action_audit.py`. Alembic migrations exist for transactions, webhooks, providers, auth state, audit integrity, outbox delivery, retention, and encrypted configuration.

Existing relevant tables include transactions, processed transactions, discrepancies, webhook configurations/deliveries, email notifications, dead letters, users/tenants, payment providers, and audit/outbox records. Some runtime paths still call `Base.metadata.create_all()`, which should remain a test/bootstrap concern rather than a production migration mechanism.

## 6. Frontend Structure

No implemented React, Vue, Next.js, or other frontend application is checked in. Frontend references in compose, CI, and documentation point to missing artifacts. The communications dashboard therefore requires a later frontend foundation after backend APIs and design-system decisions are established.

## 7. Authentication and Authorization

JWT authentication supports issuer/audience validation, key IDs and rotation, revocation, sessions, authorization versions, and tenant claims in `auth_rbac.py`. RBAC and tenant checks are present across dashboard routes. Role/permission definitions are duplicated between `role_models.py` and dashboard models, creating authorization drift risk. Some legacy routes still use an admin token rather than the JWT path.

## 8. Observability

Structured logging, correlation/request IDs, health checks, metrics payloads, Grafana configuration, Kafka circuit breaking, RQ failure callbacks, dead-letter persistence, and cryptographic audit logging are present. Provider-specific communication metrics, delivery latency, cost, wallet monitoring, and communication incidents are not yet modeled.

## 9. Reusable Components

The communications implementation should extend, not replace:

- `africas_talking.py` for the provider transport boundary
- `notifier.py` and alert templates for compatibility during migration
- `background_tasks.py`, Redis, and RQ for asynchronous work
- `producer.py` and `topics.py` for Kafka integration
- SQLAlchemy/Alembic for persistence
- `auth_rbac.py`, tenant checks, rate limiting, and `action_audit.py`
- existing health, metrics, logging, Docker, and CI conventions

## 10. Required Additions

The first production slice needs provider-neutral communication contracts, notification and delivery persistence, an outbox worker path, secure/idempotent Africa's Talking delivery webhooks, template rendering, standardized errors, and API endpoints. Later slices can add OTP, preferences, routing/failover, campaigns, costs, analytics, additional channels, and the dashboard.

## 11. Potential Conflicts

- Direct provider calls in legacy alerting can bypass the new orchestrator.
- Kafka topic configuration is currently M-Pesa-specific.
- Docker compose variants use different Kafka distributions/configuration.
- Environment variables are read directly by many modules and are not centrally normalized.
- API versioning is inconsistent: documentation requires `/v1`, while several dashboard routes remain unversioned.
- Frontend and some CI/Docker references are incomplete.
- Existing product documentation limits the active payment scope to M-Pesa, so Airtel/bank expansion must not be implied by the communications work.

## 12. Recommended Implementation Sequence

1. Add communications configuration, provider-neutral contracts, enums, and error types.
2. Add communication notifications, attempts, delivery reports, webhook events, and outbox migrations.
3. Implement the Africa's Talking SMS adapter behind the contract and route existing alert sends through a compatibility service.
4. Add asynchronous delivery, retry/dead-letter handling, signed/idempotent callbacks, and audit events.
5. Add transaction, reconciliation, fraud, and security event adapters.
6. Add tenant preferences, templates/versioning, OTP, routing/failover, cost/health metrics, and APIs.
7. Build the communications dashboard only after the API contract is stable.
8. Add USSD, voice, WhatsApp, campaigns, AI assistance, and load/chaos testing behind feature flags.
