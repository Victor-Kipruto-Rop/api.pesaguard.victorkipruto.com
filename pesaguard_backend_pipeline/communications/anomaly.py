"""Communication anomaly detection with statistical baselines.

Detects abnormal message volume, cost, delivery/failure rates, latency, and
OTP request patterns using rolling z-scores over historical aggregates, and
explains findings with supporting metrics instead of invented statistics.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Sequence

from sqlalchemy import func
from sqlalchemy.orm import Session

from .models import CommunicationAttempt, CommunicationNotification, CommunicationOtpChallenge, CommunicationWebhookEvent

_SENSITIVITY_DEFAULT = 3.0


def _sensitivity() -> float:
    try:
        return max(1.0, float(os.getenv("PESAGUARD_COMMUNICATION_ANOMALY_SENSITIVITY", str(_SENSITIVITY_DEFAULT))))
    except ValueError:
        return _SENSITIVITY_DEFAULT


def rolling_zscore(series: Sequence[float], value: float) -> float:
    """Z-score of `value` relative to `series`; returns 0.0 for tiny baselines."""
    if len(series) < 3:
        return 0.0
    mean = sum(series) / len(series)
    variance = sum((item - mean) ** 2 for item in series) / len(series)
    std = variance ** 0.5
    if std == 0:
        return 0.0 if value == mean else float("inf")
    return (value - mean) / std


def classify_anomaly(zscore: float, *, sensitivity: float | None = None) -> str | None:
    threshold = sensitivity if sensitivity is not None else _sensitivity()
    if zscore >= threshold:
        return "spike"
    if zscore <= -threshold:
        return "drop"
    return None


def _is_sqlite(session: Session) -> bool:
    return session.get_bind().dialect.name == "sqlite"


def _hour_bucket_expression(session: Session, column):
    if _is_sqlite(session):
        return func.strftime("%Y-%m-%d %H", column)
    return func.to_char(func.date_trunc("hour", column), "YYYY-MM-DD HH")


def hour_start_key(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%d %H")


def _finding(metric: str, classification: str, current: float, baseline_mean: float, zscore: float, likely_causes: list[str]) -> dict[str, Any]:
    percent = ((current - baseline_mean) / baseline_mean * 100) if baseline_mean else None
    return {
        "metric": metric,
        "classification": classification,
        "current": current,
        "baseline_mean": round(baseline_mean, 1),
        "zscore": round(zscore, 2) if zscore != float("inf") else None,
        "percent_change": round(percent, 1) if percent is not None else None,
        "likely_causes": likely_causes,
    }


def _supporting_causes(session: Session, now: datetime) -> list[str]:
    causes: list[str] = []
    hour_start = now.replace(minute=0, second=0, microsecond=0)
    failed_attempts = session.query(func.count(CommunicationAttempt.id)).filter(
        CommunicationAttempt.started_at >= hour_start,
        CommunicationAttempt.status.in_(("failed", "dead_letter")),
    ).scalar() or 0
    if failed_attempts:
        causes.append(f"{failed_attempts} failed provider attempts in the last hour")
    webhook_failures = session.query(func.count(CommunicationWebhookEvent.id)).filter(
        CommunicationWebhookEvent.received_at >= hour_start,
        CommunicationWebhookEvent.processing_status.in_(("unprocessed", "pending")),
    ).scalar() or 0
    if webhook_failures:
        causes.append(f"{webhook_failures} delivery webhooks not confirmed processed in the last hour")
    return causes or ["no supporting provider or webhook failures found in the last hour"]


def detect_communication_anomalies(session: Session, *, tenant_id: str | None = None, sensitivity: float | None = None) -> list[dict[str, Any]]:
    """Compare the current hour against the trailing 14-day hourly baseline."""
    threshold = sensitivity if sensitivity is not None else _sensitivity()
    now = datetime.now(timezone.utc)
    hour_start = now.replace(minute=0, second=0, microsecond=0)
    baseline_start = hour_start - timedelta(days=14)
    current_key = hour_start_key(hour_start)
    findings: list[dict[str, Any]] = []

    # Message volume.
    notif_filters = (CommunicationNotification.tenant_id == tenant_id,) if tenant_id else ()
    bucket_expr = _hour_bucket_expression(session, CommunicationNotification.created_at)
    rows = session.query(bucket_expr, func.count("*")).filter(CommunicationNotification.created_at >= baseline_start, *notif_filters).group_by(bucket_expr).all()
    counts = {str(bucket): float(count) for bucket, count in rows}
    series = [count for key, count in counts.items() if key != current_key]
    current = counts.get(current_key, 0.0)
    zscore = rolling_zscore(series, current)
    classification = classify_anomaly(zscore, sensitivity=threshold)
    if classification and series:
        findings.append(_finding("message_volume", classification, current, sum(series) / len(series), zscore, _supporting_causes(session, now)))

    # Failure rate per hour (failed+dead_letter / all attempts).
    attempt_filters = (CommunicationNotification.tenant_id == tenant_id,) if tenant_id else ()
    attempt_bucket = _hour_bucket_expression(session, CommunicationAttempt.started_at)
    status_rows = (
        session.query(CommunicationAttempt.status, attempt_bucket, func.count("*"))
        .join(CommunicationNotification, CommunicationNotification.id == CommunicationAttempt.notification_id)
        .filter(CommunicationAttempt.started_at >= baseline_start, *attempt_filters)
        .group_by(CommunicationAttempt.status, attempt_bucket)
        .all()
    )
    failure_rates: dict[str, float] = {}
    totals: dict[str, float] = {}
    for status, bucket, count in status_rows:
        key = str(bucket)
        totals[key] = totals.get(key, 0.0) + count
        if status in ("failed", "dead_letter"):
            failure_rates[key] = failure_rates.get(key, 0.0) + count
    baseline_rates = [failure_rates.get(key, 0.0) / totals[key] for key in totals if key != current_key and totals[key]]
    current_total = totals.get(current_key, 0.0)
    current_rate = (failure_rates.get(current_key, 0.0) / current_total) if current_total else 0.0
    zscore = rolling_zscore(baseline_rates, current_rate)
    classification = classify_anomaly(zscore, sensitivity=threshold)
    if classification and baseline_rates:
        findings.append(_finding("failure_rate", classification, round(current_rate, 4), sum(baseline_rates) / len(baseline_rates), zscore, _supporting_causes(session, now)))

    return findings


# --- OTP abuse detection ------------------------------------------------------

DEFAULT_OTP_RECIPIENT_LIMIT = 5
DEFAULT_OTP_IP_LIMIT = 20


def detect_otp_abuse(session: Session, *, window_minutes: int = 60, now: datetime | None = None) -> list[dict[str, Any]]:
    """Detect OTP request patterns that indicate enumeration or spam abuse."""
    now = now or datetime.now(timezone.utc)
    window_start = now - timedelta(minutes=window_minutes)
    try:
        recipient_limit = int(os.getenv("PESAGUARD_OTP_RECIPIENT_HOURLY_LIMIT", str(DEFAULT_OTP_RECIPIENT_LIMIT)))
    except ValueError:
        recipient_limit = DEFAULT_OTP_RECIPIENT_LIMIT
    try:
        ip_limit = int(os.getenv("PESAGUARD_OTP_IP_HOURLY_LIMIT", str(DEFAULT_OTP_IP_LIMIT)))
    except ValueError:
        ip_limit = DEFAULT_OTP_IP_LIMIT

    findings: list[dict[str, Any]] = []

    per_recipient = (
        session.query(CommunicationOtpChallenge.tenant_id, CommunicationOtpChallenge.recipient, func.count("*"))
        .filter(CommunicationOtpChallenge.created_at >= window_start)
        .group_by(CommunicationOtpChallenge.tenant_id, CommunicationOtpChallenge.recipient)
        .having(func.count("*") > recipient_limit)
        .all()
    )
    for tenant_id, recipient, count in per_recipient:
        findings.append({
            "type": "otp_flood_same_recipient",
            "tenant_id": tenant_id,
            "recipient": recipient,
            "requests": count,
            "window_minutes": window_minutes,
            "limit": recipient_limit,
            "recommended_actions": ["rate_limit_recipient", "raise_security_incident"],
        })

    per_ip = (
        session.query(CommunicationOtpChallenge.tenant_id, CommunicationOtpChallenge.ip_address, func.count("*"), func.count(func.distinct(CommunicationOtpChallenge.recipient)))
        .filter(CommunicationOtpChallenge.created_at >= window_start)
        .group_by(CommunicationOtpChallenge.tenant_id, CommunicationOtpChallenge.ip_address)
        .all()
    )
    for tenant_id, ip_address, count, distinct_recipients in per_ip:
        if ip_address and count >= ip_limit:
            findings.append({
                "type": "otp_enumeration_same_ip",
                "tenant_id": tenant_id,
                "ip_address": ip_address,
                "requests": count,
                "distinct_recipients": distinct_recipients,
                "window_minutes": window_minutes,
                "limit": ip_limit,
                "recommended_actions": ["rate_limit_ip", "temporary_block", "raise_security_incident"],
            })

    return findings