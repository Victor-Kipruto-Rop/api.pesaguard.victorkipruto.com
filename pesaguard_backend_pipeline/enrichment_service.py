"""Tenant-scoped transaction enrichment for anomaly and fraud consumers."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from statistics import mean
from typing import Any, Callable, Dict, Mapping, Optional

from ingestion import CanonicalTransaction


@dataclass(frozen=True)
class HistoricalStatistics:
    transaction_count: int = 0
    total_amount: str = "0.00"
    average_amount: str = "0.00"
    frequency_per_hour: float = 0.0
    last_transaction_at: str = ""


@dataclass(frozen=True)
class EnrichmentContext:
    merchant: Mapping[str, Any] = field(default_factory=dict)
    customer: Mapping[str, Any] = field(default_factory=dict)
    location: Mapping[str, Any] = field(default_factory=dict)
    provider: Mapping[str, Any] = field(default_factory=dict)
    account: Mapping[str, Any] = field(default_factory=dict)
    historical: HistoricalStatistics = field(default_factory=HistoricalStatistics)
    risk_profile: Mapping[str, Any] = field(default_factory=dict)
    device: Mapping[str, Any] = field(default_factory=dict)
    transaction_frequency: float = 0.0


class EnrichmentService:
    """Build a deterministic, provenance-preserving enrichment payload."""

    def __init__(
        self,
        *,
        merchant_lookup: Optional[Callable[[str, str], Mapping[str, Any]]] = None,
        customer_lookup: Optional[Callable[[str, str], Mapping[str, Any]]] = None,
        account_lookup: Optional[Callable[[str, str], Mapping[str, Any]]] = None,
        history_lookup: Optional[Callable[[str, CanonicalTransaction], HistoricalStatistics]] = None,
        risk_lookup: Optional[Callable[[str, CanonicalTransaction], Mapping[str, Any]]] = None,
        device_lookup: Optional[Callable[[str, CanonicalTransaction], Mapping[str, Any]]] = None,
    ):
        self.merchant_lookup = merchant_lookup or (lambda _tenant, _merchant: {})
        self.customer_lookup = customer_lookup or (lambda _tenant, _phone: {})
        self.account_lookup = account_lookup or (lambda _tenant, _account: {})
        self.history_lookup = history_lookup or (lambda _tenant, _transaction: HistoricalStatistics())
        self.risk_lookup = risk_lookup or (lambda _tenant, _transaction: {})
        self.device_lookup = device_lookup or (lambda _tenant, _transaction: {})

    def enrich(self, transaction: CanonicalTransaction) -> EnrichmentContext:
        historical = self.history_lookup(transaction.tenant_id, transaction)
        frequency = float(historical.frequency_per_hour)
        return EnrichmentContext(
            merchant=dict(self.merchant_lookup(transaction.tenant_id, transaction.merchant_id)),
            customer=dict(self.customer_lookup(transaction.tenant_id, transaction.phone_number)),
            location=dict(transaction.metadata.get("location") or {}),
            provider={"name": transaction.provider, "account_id": transaction.provider_account_id},
            account=dict(self.account_lookup(transaction.tenant_id, transaction.account_id)),
            historical=historical,
            risk_profile=dict(self.risk_lookup(transaction.tenant_id, transaction)),
            device=dict(self.device_lookup(transaction.tenant_id, transaction)),
            transaction_frequency=frequency,
        )

    @staticmethod
    def to_payload(context: EnrichmentContext) -> Dict[str, Any]:
        historical = context.historical
        return {
            "merchant": dict(context.merchant),
            "customer": dict(context.customer),
            "location": dict(context.location),
            "provider": dict(context.provider),
            "account": dict(context.account),
            "historical": {
                "transaction_count": historical.transaction_count,
                "total_amount": historical.total_amount,
                "average_amount": historical.average_amount,
                "frequency_per_hour": historical.frequency_per_hour,
                "last_transaction_at": historical.last_transaction_at,
            },
            "risk_profile": dict(context.risk_profile),
            "device": dict(context.device),
            "transaction_frequency": context.transaction_frequency,
        }