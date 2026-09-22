# PesaGuard Runbook

## Service health checks
1. Verify the webhook receiver and dashboard API health endpoints at http://127.0.0.1:5000/health and http://127.0.0.1:5001/health.
2. Check the Prometheus-compatible metrics endpoints for throughput, latency, and open discrepancy counts.
3. If the services are healthy but alerts are missing, review the alerting service logs and recent delivery failures.

## Kafka lag growth
1. Check the consumer lag metric and compare with recent throughput.
2. Inspect the reconciliation service logs for backpressure or database issues.
3. If lag persists for more than 10 minutes, page the operator and pause non-critical alert traffic.

## Connector authentication failure
1. Confirm the tenant credentials and token expiry state.
2. Re-run the connector sync manually and verify a successful response.
3. If failures continue, disable live alerts for that tenant and route the incident to the operator.

## Daraja callback spike
1. Validate the webhook receiver health and confirm the request volume.
2. Check for duplicate or malformed payloads that could be retried.
3. Scale the webhook receiver or rate-limit the source if the backlog continues to grow.
