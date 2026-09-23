"""Phase 9 data quality.

Defines the DQ rule contract, result/status types, and the run_data_quality
orchestrator used by the provenance layer.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Currencies and providers recognised by the DQ rule set. Shared by the rule
# implementations (dq_rules) and the orchestrator so there is one allowlist.
DQ_CURRENCY_CODES = frozenset({"KES", "USD"})
DQ_PROVIDER_ALLOWLIST = frozenset({"mpesa", "safaricom", "daraja", "africas_talking"})

LINEAGE_KEYS = ("lineage_id", "tenant_id", "event_id", "transaction_id", "provider_id")

DQ_DIMENSIONS = ["completeness", "uniqueness", "validity", "consistency", "accuracy", "timeliness"]


@dataclass(frozen=True)
class DataQualityRule:
    code: str
    dimension: str
    description: str
    expression: str


@dataclass(frozen=True)
class DataQualityFailure:
    rule: DataQualityRule
    value: Any = None
    reason: str = ""


@dataclass
class DataQualityResult:
    status: str
    transaction_id: str
    tenant_id: str
    provider_id: str
    lineage_id: str
    schema_version: Optional[str] = None
    pipeline_version: Optional[str] = None
    failures: List[DataQualityFailure] = field(default_factory=list)
    raw_payload_hash: Optional[str] = None
    profile: Optional[Dict[str, Any]] = None
    lineage_snapshot: Optional[Dict[str, Any]] = None

    @property
    def is_ok(self) -> bool:
        return self.status == DataQualityStatus.PASS

    @property
    def dimension_scores(self) -> Dict[str, float]:
        """Return a bounded 0..1 score for every declared quality dimension."""
        failed_dimensions = {failure.rule.dimension for failure in self.failures}
        return {
            dimension: 0.0 if dimension in failed_dimensions else 1.0
            for dimension in DQ_DIMENSIONS
        }

    @property
    def completeness(self) -> float:
        return self.dimension_scores["completeness"]

    @property
    def uniqueness(self) -> float:
        return self.dimension_scores["uniqueness"]

    @property
    def validity(self) -> float:
        return self.dimension_scores["validity"]

    @property
    def consistency(self) -> float:
        return self.dimension_scores["consistency"]

    @property
    def accuracy(self) -> float:
        return self.dimension_scores["accuracy"]

    @property
    def timeliness(self) -> float:
        return self.dimension_scores["timeliness"]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "transaction_id": self.transaction_id,
            "tenant_id": self.tenant_id,
            "provider_id": self.provider_id,
            "lineage_id": self.lineage_id,
            "schema_version": self.schema_version,
            "pipeline_version": self.pipeline_version,
            "failures": [self._failure_dict(f) for f in self.failures],
            "raw_payload_hash": self.raw_payload_hash,
            "profile": self.profile,
            "lineage_snapshot": self.lineage_snapshot,
        }

    @staticmethod
    def _failure_dict(failure: DataQualityFailure) -> Dict[str, Any]:
        return {
            "rule": failure.rule.code,
            "dimension": failure.rule.dimension,
            "description": failure.rule.description,
            "expression": failure.rule.expression,
            "value": str(failure.value)[:512] if failure.value is not None else None,
            "reason": failure.reason,
        }


class DataQualityStatus:
    PASS = "pass"
    FAIL = "fail"


def tx_id_from_raw(raw: Dict[str, Any]) -> str:
    for key in ("TransID", "TransactionID", "transaction_id"):
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if value is not None:
            return str(value)
    return ""


def tenant_id_from_raw(raw: Dict[str, Any]) -> str:
    for key in ("TenantID", "tenant_id", "tenantId"):
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if value is not None:
            return str(value)
    return ""


def provider_id_from_raw(raw: Dict[str, Any]) -> str:
    for key in ("Provider", "provider", "source", "provider_id"):
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().lower()
        if value is not None:
            return str(value)
    return ""


def run_data_quality(
    raw: Dict[str, Any],
    *,
    lineage: Optional[Any] = None,
    schema_version: Optional[str] = None,
    pipeline_version: Optional[str] = None,
) -> DataQualityResult:
    """Run the transaction rule set and return a serializable DQ result.

    When ``lineage`` is provided, the result carries the lineage snapshot so the
    provenance layer can persist the full exit-gate picture.
    """
    from data_lineage import build_lineage

    transaction_id = tx_id_from_raw(raw) or "unknown"
    tenant_id = tenant_id_from_raw(raw) or "unknown"
    provider_id = provider_id_from_raw(raw) or "unknown"

    if lineage is None:
        lineage = build_lineage(
            event_id=raw.get("event_id") or raw.get("TransactionType") or "event",
            transaction_id=transaction_id,
            tenant_id=tenant_id,
            provider_id=provider_id,
        )
    lineage_id = lineage.lineage_id

    from dq_rules import (
        _rule_amount_positive,
        _rule_currency_valid,
        _rule_provider_valid,
        _rule_reference_valid,
        _rule_schema_version_present,
        _rule_tenant_exists,
        _rule_transaction_id_not_null,
    )

    normalized = _normalize_payload(raw)
    rules = [
        _rule_transaction_id_not_null,
        _rule_amount_positive,
        _rule_currency_valid,
        _rule_provider_valid,
        _rule_reference_valid,
        _rule_tenant_exists,
        _rule_schema_version_present,
    ]

    failures: List[DataQualityFailure] = []
    for rule_fn in rules:
        passed, failure = rule_fn(raw, normalized)
        if not passed and failure is not None:
            failures.append(failure)

    status = DataQualityStatus.FAIL if failures else DataQualityStatus.PASS
    profile = _profile_payload(raw)
    raw_payload_hash = _json_hash(raw)
    lineage_snapshot = lineage.to_dict() if hasattr(lineage, "to_dict") else {}

    return DataQualityResult(
        status=status,
        transaction_id=transaction_id,
        tenant_id=tenant_id,
        provider_id=provider_id,
        lineage_id=lineage_id,
        schema_version=schema_version,
        pipeline_version=pipeline_version,
        failures=failures,
        raw_payload_hash=raw_payload_hash,
        profile=profile,
        lineage_snapshot=lineage_snapshot,
    )


def dq_report(result: DataQualityResult) -> Dict[str, Any]:
    """Human-consumable DQ report for lineage and audit context."""
    return {
        "status": result.status,
        "dimensions": DQ_DIMENSIONS,
        "dimension_scores": result.dimension_scores,
        "failures": result.to_dict()["failures"],
        "transaction_id": result.transaction_id,
        "tenant_id": result.tenant_id,
        "provider_id": result.provider_id,
        "schema_version": result.schema_version,
        "pipeline_version": result.pipeline_version,
    }


def _json_hash(payload: Dict[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _profile_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        return {"type": "non_object"}
    keys = list(payload.keys())
    non_empty = [k for k in keys if payload[k] not in (None, "", [], {})]
    return {
        "type": "object",
        "key_count": len(keys),
        "non_empty_key_count": len(non_empty),
        "keys": keys,
    }


def _normalize_payload(raw: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "transaction_id": raw.get("TransID") or raw.get("TransactionID") or raw.get("transaction_id"),
        "tenant_id": raw.get("TenantID") or raw.get("tenant_id") or raw.get("tenantId"),
        "provider_id": raw.get("Provider") or raw.get("provider") or raw.get("provider_id"),
        "amount": raw.get("TransAmount") or raw.get("amount"),
        "currency": raw.get("Currency") or raw.get("currency") or raw.get("TransCurrency"),
        "timestamp": raw.get("TransTime") or raw.get("transaction_time"),
        "reference": raw.get("BillRefNumber") or raw.get("Reference") or raw.get("reference"),
    }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
