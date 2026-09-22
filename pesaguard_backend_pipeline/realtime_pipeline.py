"""Schema-versioned real-time transaction stages for Redpanda consumers."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Dict, Mapping

from event_bus import EventEnvelope, build_event
from enrichment_service import EnrichmentService
from ingestion import CanonicalTransaction
from producer import publish_versioned_event


class PipelineContractError(ValueError):
    """Raised when an event cannot advance to the next stream stage."""


def _child_event(parent: EventEnvelope, event_type: str, payload: Dict[str, Any]) -> EventEnvelope:
    return build_event(
        event_type,
        parent.tenant_id,
        parent.aggregate_id,
        payload,
        correlation_id=parent.correlation_id,
        source=parent.source,
        source_event_id=parent.source_event_id or parent.event_id,
        causation_id=parent.event_id,
        producer="pesaguard.realtime_pipeline",
        producer_version="1",
        schema_version=parent.schema_version,
        metadata={**parent.metadata, "parent_event_id": parent.event_id},
    )


def validate_transaction_payload(payload: Mapping[str, Any]) -> Dict[str, Any]:
    """Validate the provider-neutral fields required by downstream consumers."""
    required = ("TransID", "TransAmount", "Currency", "provider", "provider_account_id")
    missing = [field for field in required if not str(payload.get(field) or "").strip()]
    if missing:
        raise PipelineContractError(f"transaction event is missing fields: {', '.join(missing)}")
    try:
        if Decimal(str(payload["TransAmount"])) <= 0:
            raise PipelineContractError("transaction amount must be greater than zero")
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise PipelineContractError("transaction amount must be a valid decimal") from exc
    return dict(payload)


def normalize_transaction_payload(payload: Mapping[str, Any]) -> Dict[str, Any]:
    """Produce the stable canonical transaction payload used by workers."""
    validated = validate_transaction_payload(payload)
    normalized = dict(validated)
    normalized["TransID"] = str(validated["TransID"]).strip()
    normalized["provider"] = str(validated["provider"]).strip().lower()
    normalized["provider_account_id"] = str(validated["provider_account_id"]).strip()
    normalized["Currency"] = str(validated["Currency"]).strip().upper()
    normalized["TransAmount"] = str(Decimal(str(validated["TransAmount"])).quantize(Decimal("0.01")))
    return normalized


class RealtimeTransactionPipeline:
    """Publish staged events; PostgreSQL remains the authoritative state store."""

    def __init__(self, publisher: Callable[..., Any] = publish_versioned_event, stage_recorder: Callable[..., Any] | None = None, enricher: EnrichmentService | None = None):
        self.publisher = publisher
        self.stage_recorder = stage_recorder
        self.enricher = enricher or EnrichmentService()

    def _publish(self, event: EventEnvelope, stage: str) -> EventEnvelope:
        if self.stage_recorder is not None:
            self.stage_recorder(event, stage, event.payload)
        self.publisher(event)
        return event

    def validate(self, event: EventEnvelope) -> EventEnvelope:
        payload = validate_transaction_payload(event.payload)
        return self._publish(_child_event(event, "transaction.validated", payload), "VALIDATED")

    def normalize(self, event: EventEnvelope) -> EventEnvelope:
        payload = normalize_transaction_payload(event.payload)
        return self._publish(_child_event(event, "transaction.normalized", payload), "NORMALIZED")

    def process(self, event: EventEnvelope) -> EventEnvelope:
        # Persistence/reconciliation workers consume this event and write state
        # through their existing PostgreSQL transaction/outbox boundaries.
        return self._publish(_child_event(event, "transaction.processed", dict(event.payload)), "PROCESSED")

    def enrich(self, event: EventEnvelope) -> EventEnvelope:
        enriched = dict(event.payload)
        transaction = _canonical_from_event(event)
        enriched["enrichment"] = EnrichmentService.to_payload(self.enricher.enrich(transaction))
        enriched["enrichment"]["enriched_by"] = "pesaguard.realtime_pipeline"
        return self._publish(_child_event(event, "transaction.enriched", enriched), "ENRICHED")


def _canonical_from_event(event: EventEnvelope) -> CanonicalTransaction:
    payload = event.payload
    return CanonicalTransaction(
        tenant_id=event.tenant_id,
        provider=str(payload.get("provider") or "unknown"),
        provider_account_id=str(payload.get("provider_account_id") or payload.get("BusinessShortCode") or "unknown"),
        transaction_id=str(payload.get("transaction_id") or event.aggregate_id),
        provider_transaction_id=str(payload.get("provider_transaction_id") or payload.get("TransID") or event.aggregate_id),
        account_id=str(payload.get("account_id") or payload.get("provider_account_id") or "unknown"),
        amount=str(payload.get("amount") or payload.get("TransAmount") or "0.00"),
        currency=str(payload.get("currency") or payload.get("Currency") or "KES"),
        transaction_type=str(payload.get("transaction_type") or payload.get("TransactionType") or "PAYMENT"),
        status=str(payload.get("status") or payload.get("Status") or "RECEIVED"),
        transaction_time=str(payload.get("transaction_time") or payload.get("TransTime") or event.occurred_at),
        phone_number=str(payload.get("phone_number") or payload.get("MSISDN") or "unknown"),
        merchant_id=str(payload.get("merchant_id") or ""),
        source=str(payload.get("source") or event.source),
        metadata=dict(payload.get("metadata") or {}),
        created_at=str(payload.get("created_at") or event.occurred_at),
        updated_at=str(payload.get("updated_at") or event.occurred_at),
    )