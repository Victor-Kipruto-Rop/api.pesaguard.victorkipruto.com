#!/bin/sh
set -eu

# Ensure Python path includes application root directories
export PYTHONPATH="${PYTHONPATH:-}:/app:/app/pesaguard_backend_pipeline"

# Resolve Redis URL from environment or default to local service
REDIS_URL="${REDIS_URL:-redis://redis:6379/0}"

# Configure RQ worker queues (prioritizing critical alerts and webhooks over general events)
# Format: space-separated list of queues in order of priority
RQ_QUEUES="${RQ_QUEUE_NAME:-critical_alerts transaction_events webhooks default}"

echo "Starting PesaGuard RQ Worker..."
echo "  - Redis URL: ${REDIS_URL}"
echo "  - Queues   : ${RQ_QUEUES}"
echo "  - Python Path: ${PYTHONPATH}"

if [ "${COMMUNICATION_WORKER_MODE:-0}" = "1" ]; then
  exec python -m pesaguard_backend_pipeline.communications.worker
fi

# Execute RQ worker with graceful shutdown timeout (e.g., 60 seconds)
exec rq worker \
  --path /app \
  --path /app/pesaguard_backend_pipeline \
  --url "${REDIS_URL}" \
  --worker-class rq.Worker \
  ${RQ_QUEUES}
