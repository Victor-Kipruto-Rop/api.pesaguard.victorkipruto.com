# PesaGuard Setup

## Environment setup

1. Create a Python virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt pytest pyyaml sqlalchemy psycopg2-binary requests
   ```
2. Copy the sample environment file if present and fill in the required values:
   ```bash
   cp .env.example .env 2>/dev/null || true
   ```
3. Provide the minimum runtime settings:
   - `DATABASE_URL` for Postgres
   - `KAFKA_BOOTSTRAP_SERVERS`
   - `TENANT_ID`
   - `CONNECTOR_TYPE` (`postgres`, `rest`, or `google_sheets`)
   - `SLACK_WEBHOOK_URL` (optional)

## Running locally

```bash
docker-compose up -d postgres kafka
alembic upgrade head
python app.py
python reconciliation_job.py
```

Production and shared development databases must be migrated with Alembic before
starting the services. Runtime schema creation is disabled for PostgreSQL.

## Running tests

```bash
pytest -q
```

## Onboarding a pilot tenant

- Create a tenant-specific connector mapping and set the environment variables.
- Confirm that the connector exposes records with `internal_ref`, `amount`, `phone_number`, `timestamp`, and `status`.
- Run the reconciliation flow in shadow mode for at least one business day.
- Review the generated discrepancies and tune thresholds before enabling live alerts.

## Operational notes

- The reconciliation engine treats duplicate callbacks and missing-payment cases as critical and records them in the discrepancy stream.
- The connector layer is designed to be tenant-scoped so new customers can be onboarded by changing configuration rather than rewriting business logic.
- If a Daraja callback shape changes, validate it against the sandbox and update the payload validator before production use.

## Alerting, monitoring, and dashboards

- Alerts are routed through the alerting service with severity-aware channels and deduplication support.
- Each service exposes a Prometheus-compatible /metrics endpoint, and the dashboard API returns a text/plain payload for Prometheus scraping.
- A Grafana dashboard definition is available at [monitoring/grafana-dashboard.json](../monitoring/grafana-dashboard.json).
- For local verification, run the backend services and scrape http://127.0.0.1:5000/metrics and http://127.0.0.1:5001/metrics.
- A simple operator runbook should cover Kafka lag, connector auth failures, and unexpected Daraja callback spikes.
