import json
import logging
from pathlib import Path

from event_bus import build_event, consumer_lag_registry
from event_consumer import ConsumerGroup, EventConsumer
from logging_utils import JsonFormatter, bind_observability_context, get_observability_context
from data_quality import run_data_quality
from metrics import record_business_metric, record_data_quality, record_event_retry, record_http_request, record_pipeline_event, telemetry_snapshot
from producer import publish_versioned_event


def test_structured_log_contains_full_traceability_context():
    bind_observability_context(
        request_id="req-1",
        correlation_id="corr-1",
        transaction_id="tx-1",
        event_id="evt-1",
        trace_id="trace-1",
        tenant_id="tenant-a",
    )
    record = logging.LogRecord("test", logging.INFO, __file__, 1, "trace test", (), None)
    payload = json.loads(JsonFormatter().format(record))
    assert {payload[key] for key in ("request_id", "correlation_id", "transaction_id", "event_id", "trace_id", "tenant_id")} == {
        "req-1", "corr-1", "tx-1", "evt-1", "trace-1", "tenant-a",
    }


def test_transaction_trace_context_survives_kafka_and_consumer_boundaries():
    event = build_event("transaction.received", "tenant-a", "tx-trace", {"TransID": "tx-trace"}, event_id="evt-trace", correlation_id="corr-trace")
    sent = {}

    class Producer:
        def send(self, topic, **kwargs):
            sent.update(topic=topic, **kwargs)
            return sent

    publish_versioned_event(event, producer=Producer())
    consumer = EventConsumer(ConsumerGroup("audit", frozenset({"transaction.received"})))
    consumer.register("transaction.received", lambda received: None)
    assert consumer.consume(event).status == "processed"
    context = get_observability_context()
    assert context["transaction_id"] == "tx-trace"
    assert context["event_id"] == "evt-trace"
    assert context["request_id"] == event.request_id or not event.request_id
    assert context["correlation_id"] == "corr-trace"
    assert context["tenant_id"] == "tenant-a"
    assert context["trace_id"]


def test_application_business_retry_and_lag_metrics_are_recorded():
    record_http_request(10, status_code=200)
    record_http_request(50, status_code=500, timeout=True)
    record_business_metric("transactions_received")
    record_business_metric("fraud_engine_failures")
    record_event_retry()
    consumer_lag_registry.update("reconciliation", {0: 12, 1: 3})
    snapshot = telemetry_snapshot()
    assert snapshot["requests"] >= 2
    assert snapshot["error_rate"] > 0
    assert snapshot["timeouts"] >= 1
    assert snapshot["event_retries"] >= 1
    assert snapshot["business"]["fraud_engine_failures"] >= 1
    assert sum(consumer_lag_registry.snapshot()["reconciliation"].values()) == 15


def test_pipeline_metrics_record_tenant_scoped_outcomes_and_latency():
    for outcome in ("entered", "succeeded", "duplicate", "failed", "retried", "dead_lettered"):
        record_pipeline_event(outcome, tenant_id="tenant-observability", duration_ms=12.5)

    snapshot = telemetry_snapshot()
    for outcome in ("entered", "succeeded", "duplicate", "failed", "retried", "dead_lettered"):
        assert snapshot["business"][f"pipeline_{outcome}"] >= 1


def test_data_quality_metrics_accept_dimension_scores():
    result = run_data_quality({
        "TransID": "quality-metric-1",
        "TenantID": "tenant-observability",
        "Provider": "mpesa",
        "TransAmount": "10.00",
        "Currency": "KES",
        "BillRefNumber": "ref-1",
        "schema_version": "1.0",
    })
    record_data_quality(result)
    assert result.dimension_scores["validity"] == 1.0


def test_phase5_alert_rules_cover_required_failure_domains():
    content = Path("monitoring/alerts.yml").read_text(encoding="utf-8")
    for alert_metric in (
        "pesaguard_error_rate",
        "pesaguard_request_p99_ms",
        "pesaguard_db_pool_usage",
        "pesaguard_kafka_consumer_lag_max",
        "pesaguard_event_retries_total",
        "pesaguard_business_fraud_engine_failures",
        "pesaguard_business_reconciliation_failures",
        "pesaguard_business_security_events",
    ):
        assert alert_metric in content
