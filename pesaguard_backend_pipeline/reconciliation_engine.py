"""
Reconciliation Engine for matching M-Pesa Daraja callbacks to internal ledger records.

Turns raw webhook events into auditable reconciliation outcomes so operational teams
can distinguish between exact matches, partial matches, missing payments, and duplicate callbacks.
"""

from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Set

from event_store import ProcessResult
from reconciliation_scoring import score_match

# Import normalization helpers (added in feat/phase1-reconciliation-systematic)
try:
    from .reconciliation_utils import normalize_daraja_event, time_window_match
except ImportError:  # pragma: no cover - fallback for top-level script execution
    from reconciliation_utils import normalize_daraja_event, time_window_match

logger = logging.getLogger("pesaguard.reconciliation_engine")


def evaluate_transaction(
    event: Dict[str, Any],
    internal_records: Sequence[Dict[str, Any]],
    seen_trans_ids: Set[str],
    window_minutes: int = 15,
    tenant_settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Evaluate one M-Pesa event against a set of internal records.

    Args:
        event: Daraja callback payload dict
        internal_records: List of internal order/payment dicts
        seen_trans_ids: Set of recently observed transaction IDs
        window_minutes: Default matching time window in minutes
        tenant_settings: Optional tenant-specific settings dict for custom rules

    Returns:
        Structured evaluation outcome dict
    """
    # Normalize incoming event into canonical keys without discarding original keys.
    # This preserves backwards compatibility while centralizing parsing/format logic.
    try:
        norm = normalize_daraja_event(event, tenant_id=str(tenant_settings.get("tenant_id")) if tenant_settings else "default")
    except Exception:
        norm = {}
    # Merge normalized canonical keys into the event for the rest of the engine to use.
    merged_event = dict(event or {})
    merged_event.update(norm or {})
    event = merged_event

    trans_id = str(event.get("TransID") or event.get("trans_id") or "unknown").strip()
    duplicate = trans_id in seen_trans_ids

    anomalies: List[str] = []
    if duplicate:
        anomalies.append("duplicate_transaction_id")

    event_time = _parse_event_time(event.get("TransTime"))
    if event_time:
        latency = (datetime.now(timezone.utc) - event_time).total_seconds()
        if latency > 3600:
            anomalies.append("late_arriving_event")

    amount = _coerce_amount(event.get("TransAmount") or event.get("amount"))
    if amount is None or amount <= 0:
        anomalies.append("invalid_or_zero_amount")

    # Resolve tenant config overrides
    reconciliation_cfg = (tenant_settings or {}).get("reconciliation", {}) if tenant_settings else {}
    tolerance_percent = Decimal(str(reconciliation_cfg.get("tolerance_percent", "0.5")))
    allow_partial = bool(reconciliation_cfg.get("allow_partial", True))
    
    if reconciliation_cfg.get("window_minutes") is not None:
        try:
            window_minutes = int(reconciliation_cfg["window_minutes"])
        except (TypeError, ValueError):
            pass

    if not internal_records:
        return {
            "trans_id": trans_id,
            "status": "missing_payment",
            "severity": "critical",
            "duplicate": duplicate,
            "anomalies": anomalies,
            "match": {"match_type": "none", "reason": "no_internal_records"},
        }

    best_match = _find_best_match(
        event,
        internal_records,
        window_minutes=window_minutes,
        tolerance_percent=tolerance_percent,
        allow_partial=allow_partial,
    )

    if best_match is None:
        return {
            "trans_id": trans_id,
            "status": "missing_payment",
            "severity": "critical",
            "duplicate": duplicate,
            "anomalies": anomalies,
            "match": {"match_type": "none", "reason": "no_matching_record"},
        }

    if best_match["match_type"] in {"exact", "fuzzy_exact"}:
        return {
            "trans_id": trans_id,
            "status": "matched",
            "severity": "info",
            "duplicate": duplicate,
            "anomalies": anomalies,
            "match": best_match,
        }

    return {
        "trans_id": trans_id,
        "status": "needs_review",
        "severity": "warning",
        "duplicate": duplicate,
        "anomalies": anomalies,
        "match": best_match,
    }


def _find_best_match(
    event: Dict[str, Any],
    internal_records: Sequence[Dict[str, Any]],
    window_minutes: int = 15,
    tolerance_percent: Decimal = Decimal("0.5"),
    allow_partial: bool = True,
) -> Optional[Dict[str, Any]]:
    """Match callback event against candidate internal records."""
    amount = _coerce_amount(event.get("TransAmount") or event.get("amount"))
    if amount is None or amount <= 0:
        return None

    phone = str(event.get("MSISDN") or event.get("phone_number") or "").strip()
    event_time = _parse_event_time(event.get("TransTime"))
    allowed_delta = max(Decimal("0.01"), abs(amount) * (tolerance_percent / Decimal("100")))

    candidates = []
    for record in internal_records:
        record_time = _parse_record_time(record.get("timestamp") or record.get("synced_at") or record.get("created_at"))
        
        latency = 0
        if record_time is not None and event_time is not None:
            latency = int(abs((event_time - record_time).total_seconds()))
            if latency > window_minutes * 60:
                continue

        record_amount = _coerce_amount(record.get("amount"))
        if record_amount is None:
            continue

        amt_diff = abs(record_amount - amount)
        if amt_diff > allowed_delta:
            continue

        record_phone = str(record.get("phone_number") or record.get("msisdn") or "").strip()
        phone_matches = record_phone == phone and len(phone) > 0

        if phone_matches and amt_diff == 0:
            match_type = "exact"
        elif phone_matches and amt_diff <= allowed_delta:
            match_type = "fuzzy_exact"
        elif not phone_matches and allow_partial:
            match_type = "partial_fuzzy" if amt_diff <= allowed_delta else "partial"
        else:
            continue

        candidate_score, candidate_reasons = score_match(event, record)
        candidates.append({
            "match_type": match_type,
            "internal_ref": record.get("internal_ref"),
            "record": record,
            "latency_seconds": latency,
            "amount_diff": amt_diff,
            "score": candidate_score,
            "reasons": candidate_reasons,
        })

    if not candidates:
        return None

    priority = {"exact": 0, "fuzzy_exact": 1, "partial_fuzzy": 2, "partial": 3}
    candidates.sort(
        key=lambda item: (
            -item.get("score", 0.0),
            priority.get(item["match_type"], 99),
            item["latency_seconds"],
            item["amount_diff"],
        )
    )
    return candidates[0]


def _coerce_amount(value: Any) -> Optional[Decimal]:
    """Safely parse monetary values as fixed-precision decimals."""
    if value is None:
        return None
    try:
        val = Decimal(str(value)).quantize(Decimal("0.01"))
        return val if val >= 0 else None
    except (InvalidOperation, TypeError, ValueError):
        return None


def _parse_event_time(value: Any) -> Optional[datetime]:
    """Parse M-Pesa 14-digit Daraja timestamp strings or ISO timestamps into UTC datetimes."""
    if not value:
        return None

    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    text = str(value).strip()
    if len(text) == 14 and text.isdigit():
        try:
            return datetime.strptime(text, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
        except ValueError:
            return None

    if text.endswith("Z"):
        text = text[:-1] + "+00:00"

    try:
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


def _parse_record_time(value: Any) -> Optional[datetime]:
    return _parse_event_time(value)


def reconcile_with_idempotency(
    event: Dict[str, Any],
    internal_records: Sequence[Dict[str, Any]],
    event_store: Any,
    discrepancy_dao: Any,
    session: Any,
    tenant_id: Optional[str] = None,
    tenant_settings: Optional[Dict[str, Any]] = None,
    window_minutes: int = 15,
    source_ip: Optional[str] = None,
    signature_verified: bool = False,
) -> Dict[str, Any]:
    """Atomically evaluate and record reconciliation outcomes inside a single database transaction.

    Ensures that both the idempotency ledger write and the Discrepancy write commit
    together or roll back entirely.
    """
    trans_id = str(event.get("TransID") or event.get("trans_id") or "unknown").strip()
    account_id = str(event.get("provider_account_id") or event.get("BusinessShortCode") or event.get("business_short_code") or "legacy-default")

    # Pre-flight duplicate check optimization
    if event_store and event_store.already_processed(trans_id, tenant_id=tenant_id, provider_account=account_id):
        logger.info("Idempotency: duplicate trans_id=%s detected prior to evaluation, skipping", trans_id)
        return {
            "trans_id": trans_id,
            "status": "duplicate_ignored",
            "severity": "info",
            "anomalies": ["duplicate_transaction_id"],
        }

    seen_trans_ids: Set[str] = set()
    evaluation = evaluate_transaction(
        event,
        internal_records,
        seen_trans_ids,
        window_minutes=window_minutes,
        tenant_settings=tenant_settings,
    )
    evaluation["tenant_id"] = tenant_id or "default"
    evaluation["event"] = event

    try:
        result = ProcessResult.STORED
        if event_store:
            result = event_store.mark_processed_in_session(
                session,
                event,
                tenant_id=tenant_id,
                source_ip=source_ip,
                signature_verified=signature_verified,
            )

        if result == ProcessResult.DUPLICATE:
            session.rollback()
            logger.info("Duplicate trans_id=%s caught during idempotency session flush, skipping", trans_id)
            return {
                "trans_id": trans_id,
                "status": "duplicate_ignored",
                "severity": "info",
                "anomalies": ["duplicate_transaction_id"],
            }

        if result == ProcessResult.ERROR:
            session.rollback()
            raise RuntimeError(f"mark_processed_in_session failed validation for trans_id={trans_id}")

        # Record discrepancy for non-matched or anomalous transactions
        if evaluation.get("status") in {"needs_review", "missing_payment"} or evaluation.get("anomalies"):
            if discrepancy_dao:
                disc_id = f"{trans_id}-{evaluation.get('status', 'unknown')}"
                discrepancy_dao.save_discrepancy(
                    session=session,
                    id=disc_id,
                    trans_id=trans_id,
                    tenant_id=tenant_id,
                    anomaly_type=evaluation.get("status", "unknown"),
                    severity=evaluation.get("severity", "warning"),
                    details=evaluation,
                )

        session.commit()
        evaluation["duplicate"] = False
        return evaluation

    except Exception as exc:
        logger.exception("Error during atomic reconciliation for trans_id=%s — rolling back: %s", trans_id, exc)
        session.rollback()
        raise
