"""Small canonical data-engineering pipeline used by API, event, and batch paths."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, Iterable, Mapping, Optional

from normalization import normalize_amount, normalize_currency, normalize_identifier, normalize_timestamp


@dataclass(frozen=True)
class Lineage:
    stages: tuple[str, ...] = ("raw", "validated", "normalized")

    def has_stage(self, stage: str) -> bool:
        return stage.lower() in self.stages


@dataclass(frozen=True)
class CanonicalRecord:
    event_id: str
    tenant_id: str
    provider_transaction_id: str
    amount: Decimal
    currency: str
    occurred_at: datetime
    raw_payload: Mapping[str, Any]
    lineage: Lineage = field(default_factory=Lineage)


class InMemoryDataRepository:
    def __init__(self):
        self._records: list[CanonicalRecord] = []
        self.archived: list[CanonicalRecord] = []

    def add(self, record: CanonicalRecord) -> None:
        self._records.append(record)

    def records(self, tenant_id: str) -> Iterable[CanonicalRecord]:
        return (record for record in self._records if record.tenant_id == tenant_id)

    def archive(self, record: CanonicalRecord) -> None:
        self.archived.append(record)
        self._records.remove(record)


class CoreDataEngineering:
    def __init__(self, repository: Optional[InMemoryDataRepository] = None):
        self.repository = repository or InMemoryDataRepository()
        self._identity_keys: set[tuple[str, str]] = set()
        self._lineage: Dict[tuple[str, str], Lineage] = {}

    def _normalize(self, tenant_id: str, payload: Mapping[str, Any]) -> CanonicalRecord:
        provider_transaction_id = normalize_identifier(payload.get("TransID") or payload.get("transaction_id"))
        event_id = "evt_" + hashlib.sha256(f"{tenant_id}:{provider_transaction_id}".encode()).hexdigest()[:24]
        occurred_at = datetime.fromisoformat(normalize_timestamp(payload.get("TransTime") or payload.get("timestamp"), default_timezone="Africa/Nairobi").replace("Z", "+00:00"))
        return CanonicalRecord(
            event_id=event_id,
            tenant_id=tenant_id,
            provider_transaction_id=provider_transaction_id,
            amount=Decimal(normalize_amount(payload.get("TransAmount") or payload.get("amount"))),
            currency=normalize_currency(payload.get("Currency") or payload.get("currency")),
            occurred_at=occurred_at,
            raw_payload=dict(payload),
        )

    def _ingest(self, tenant_id: str, payload: Mapping[str, Any]) -> Optional[CanonicalRecord]:
        identity = (tenant_id, normalize_identifier(payload.get("TransID") or payload.get("transaction_id")))
        if identity in self._identity_keys:
            return None
        try:
            record = self._normalize(tenant_id, payload)
        except (ValueError, TypeError, KeyError):
            return None
        self._identity_keys.add(identity)
        self.repository.add(record)
        self._lineage[(tenant_id, record.event_id)] = record.lineage
        return record

    def ingest_api(self, tenant_id: str, payload: Mapping[str, Any]) -> Optional[CanonicalRecord]:
        return self._ingest(tenant_id, payload)

    def ingest_event(self, tenant_id: str, payload: Mapping[str, Any]) -> Optional[CanonicalRecord]:
        return self._ingest(tenant_id, payload)

    def ingest_batch(self, tenant_id: str, payloads: Iterable[Mapping[str, Any]]) -> Dict[str, int]:
        summary = {"accepted": 0, "duplicates": 0, "rejected": 0}
        for payload in payloads:
            try:
                identity = (tenant_id, normalize_identifier(payload.get("TransID") or payload.get("transaction_id")))
            except (ValueError, TypeError):
                summary["rejected"] += 1
                continue
            if identity in self._identity_keys:
                summary["duplicates"] += 1
                continue
            if self._ingest(tenant_id, payload) is None:
                summary["rejected"] += 1
            else:
                summary["accepted"] += 1
        return summary

    def ingest_connector(self, connector: Any, tenant_id: str) -> Dict[str, int]:
        return self.ingest_batch(tenant_id, connector.read(tenant_id=tenant_id))

    def lineage_for(self, tenant_id: str, event_id: str) -> Lineage:
        return self._lineage[(tenant_id, event_id)]

    def aggregate(self, tenant_id: str) -> Dict[str, Dict[str, Any]]:
        result: Dict[str, Dict[str, Any]] = {}
        for record in self.repository.records(tenant_id):
            metric = result.setdefault(record.currency, {"count": 0, "amount": Decimal("0.00")})
            metric["count"] += 1
            metric["amount"] += record.amount
        return {currency: {"count": data["count"], "amount": f"{data['amount']:.2f}"} for currency, data in result.items()}

    def partition_key(self, record: CanonicalRecord) -> str:
        return f"tenant={record.tenant_id}/year={record.occurred_at.year:04d}/month={record.occurred_at.month:02d}"

    def apply_retention(self, tenant_id: str, *, now: Optional[datetime] = None, retention_days: int = 365) -> int:
        current = now or datetime.now(timezone.utc)
        cutoff = current - timedelta(days=retention_days)
        expired = [record for record in self.repository.records(tenant_id) if record.occurred_at <= cutoff]
        for record in expired:
            self.repository.archive(record)
        return len(expired)