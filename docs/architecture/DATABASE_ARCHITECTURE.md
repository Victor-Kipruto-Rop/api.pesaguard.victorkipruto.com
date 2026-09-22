# PesaGuard Data Architecture

PesaGuard uses a Python Flask backend with SQLAlchemy and PostgreSQL as the authoritative data model for application tables such as transaction records, discrepancies, dead-letter records, and action audit metadata. The repository also uses Redis for request throttling and queue dispatch, and Kafka for transaction event publication. SQLite databases exist in the repository for local tests and samples.

## Data flow

1. Webhook or API request enters the Flask service.
2. Request is validated and rate limited.
3. Event store or service logic writes or processes records.
4. Transaction events are published to Redis/RQ and, where configured, Kafka.
5. Reconciliation and discrepancy services update operational records and reports.

## Persistence layers

- PostgreSQL / SQLAlchemy: primary structured persistence.
- Redis: queueing, caching, and rate limiting.
- Kafka: streaming boundary for transaction events.
- SQLite: test and demo local storage.

## Data protection posture

Financial and customer-sensitive data should not be sent to Sentry automatically. Use safe metadata, request IDs, correlation IDs, and provider/service tags instead. Avoid logging or capturing secrets, credentials, tokens, PINs, bank account identifiers, or API keys.
