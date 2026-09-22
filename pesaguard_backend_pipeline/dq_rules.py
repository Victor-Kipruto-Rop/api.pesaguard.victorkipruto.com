"""Phase 9 data-quality rule implementations.

Each rule returns (passed, failure_or_none). A None failure means the
rule passed. The rule contract is shared between the orchestrator and any
validator wrappers used by tests or processors.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from data_quality import DataQualityFailure, DataQualityRule


def _pick_string(payload: Dict[str, Any], *keys: str) -> Optional[str]:
    for key in keys:
        if key in payload:
            candidate = payload[key]
            if isinstance(candidate, str):
                return candidate.strip()
            if isinstance(candidate, (int, float)):
                return str(candidate)
    return None



def _try_amount(payload: Dict[str, Any], *keys: str) -> Optional[float]:
    for key in keys:
        if key in payload:
            try:
                return float(payload[key])
            except (TypeError, ValueError):
                return None
    return None


def _parse_timestamp(value: str) -> Optional[datetime]:
    normalized = value.strip().replace(" ", "T", 1)
    for fmt in ("%Y%m%dT%H%M%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S"):
        try:
            dt = datetime.strptime(normalized.replace("+0000", "+00:00"), fmt)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except ValueError:
            continue
    return None

def _rule_transaction_id_not_null(raw: Dict[str, Any], normalized: Optional[Dict[str, Any]]) -> Tuple[bool, Optional[DataQualityFailure]]:
    value = _pick_string(raw, "TransactionID", "TransID", "transaction_id", "trans_id")
    if value and value.strip():
        return True, None
    return False, DataQualityFailure(
        rule=DataQualityRule("transaction_id_not_null", "completeness", "Transaction identifier must be present", "transaction_id IS NOT NULL"),
        value=value,
        reason="transaction identifier is missing or empty",
    )


def _rule_amount_positive(raw: Dict[str, Any], normalized: Optional[Dict[str, Any]]) -> Tuple[bool, Optional[DataQualityFailure]]:
    value = _try_amount(raw, "TransAmount", "amount", "TransTotal")
    if value is None:
        return False, DataQualityFailure(
            rule=DataQualityRule("amount_positive", "validity", "Transaction amount must be greater than zero", "amount > 0"),
            value=None,
            reason="amount is missing or not numeric",
        )
    if value > 0:
        return True, None
    return False, DataQualityFailure(
        rule=DataQualityRule("amount_positive", "validity", "Transaction amount must be greater than zero", "amount > 0"),
        value=value,
        reason=f"amount must be greater than zero, got {value}",
    )


def _rule_currency_valid(raw: Dict[str, Any], normalized: Optional[Dict[str, Any]]) -> Tuple[bool, Optional[DataQualityFailure]]:
    value = _pick_string(raw, "Currency", "CurrencyCode", "currency", "currency_code")
    if value and value.strip().upper() in {"KES", "USD"}:
        return True, None
    return False, DataQualityFailure(
        rule=DataQualityRule("currency_valid", "validity", "Currency must be a supported value", "currency in KES, USD"),
        value=value,
        reason=f"unsupported currency: {value!r}",
    )


def _rule_provider_valid(raw: Dict[str, Any], normalized: Optional[Dict[str, Any]]) -> Tuple[bool, Optional[DataQualityFailure]]:
    value = _pick_string(raw, "Provider", "provider", "source", "provider_id")
    if value and value.strip().lower() in {"mpesa", "safaricom", "daraja", "africas_talking"}:
        return True, None
    return False, DataQualityFailure(
        rule=DataQualityRule("provider_valid", "validity", "Provider must be recognized", "provider in known set"),
        value=value,
        reason=f"unrecognized provider: {value!r}",
    )


def _rule_reference_valid(raw: Dict[str, Any], normalized: Optional[Dict[str, Any]]) -> Tuple[bool, Optional[DataQualityFailure]]:
    value = _pick_string(raw, "BillRefNumber", "BillReferenceNumber", "reference", "reference_number", "AccountReference")
    if value and value.strip():
        return True, None
    return False, DataQualityFailure(
        rule=DataQualityRule("reference_valid", "consistency", "Reference identifier must be present where required", "reference present"),
        value=value,
        reason="reference identifier is missing or empty",
    )


def _rule_tenant_exists(raw: Dict[str, Any], normalized: Optional[Dict[str, Any]]) -> Tuple[bool, Optional[DataQualityFailure]]:
    value = _pick_string(raw, "tenant_id", "TenantID", "ClientID", "client_id")
    if value and value.strip():
        return True, None
    return False, DataQualityFailure(
        rule=DataQualityRule("tenant_exists", "consistency", "Tenant must exist in the system", "tenant exists"),
        value=value,
        reason="tenant identifier is missing or empty",
    )


def _rule_schema_version_present(raw: Dict[str, Any], normalized: Optional[Dict[str, Any]]) -> Tuple[bool, Optional[DataQualityFailure]]:
    value = _pick_string(raw, "schema_version", "SchemaVersion", "version", "event_version")
    if value and value.strip():
        return True, None
    return False, DataQualityFailure(
        rule=DataQualityRule("schema_version_present", "consistency", "Payload must declare a recognized schema version", "schema version present"),
        value=value,
        reason="schema version is missing or empty",
    )

