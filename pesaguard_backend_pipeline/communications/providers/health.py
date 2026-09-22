"""Provider health scoring from persisted delivery outcomes.

The score aggregates real delivery data (success rate, latency, timeout rate,
delivery rate, webhook health) over a configurable window so dashboards and
the failover policy operate on actual evidence rather than assumptions.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import CommunicationAttempt, CommunicationIncident, CommunicationNotification, CommunicationWebhookEvent


class HealthLevel(StrEnum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    CRITICAL = "CRITICAL"
    OUTAGE = "OUTAGE"


DEFAULT_WINDOW_HOURS = 24


def _window_hours() -> int:
    try:
        return max(1, int(os.getenv("PESAGUARD_COMMUNICATION_HEALTH_WINDOW_HOURS", str(DEFAULT_WINDOW_HOURS))))
    except ValueError:
        return DEFAULT_WINDOW_HOURS


def _level(score: float, success_rate: float) -> HealthLevel:
    if success_rate <= 0.5:
        return HealthLevel.OUTAGE
    if score >= 90:
        return HealthLevel.HEALTHY
    if score >= 70:
        return HealthLevel.DEGRADED
    return HealthLevel.CRITICAL


def provider_health_snapshot(session: Session, provider: str, *, window_hours: int | None = None) -> dict[str, Any]:
    """Compute a 0-100 health score for one provider from real outcomes."""
    hours = window_hours or _window_hours()
    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    attempts = session.query(
        CommunicationAttempt.status,
        func.count(CommunicationAttempt.id),
        func.avg(CommunicationAttempt.latency_ms),
    ).filter(
        CommunicationAttempt.provider == provider,
        CommunicationAttempt.started_at >= since,
    ).group_by(CommunicationAttempt.status).all()

    total = sum(count for _, count, _ in attempts) or 0
    by_status: dict[str, int] = {}
    latencies: list[float] = []
    for status, count, avg_latency in attempts:
        by_status[status] = count
        if avg_latency is not None:
            latencies.append(float(avg_latency))
    success_total = sum(count for status, count in by_status.items() if status in {"accepted", "submitted", "sent", "delivered"})
    failures = sum(count for status, count in by_status.items() if status in {"failed", "dead_letter", "retrying"})
    timeouts = by_status.get("retrying", 0)
    success_rate = round(success_total / total, 4) if total else 1.0
    failure_rate = round(failures / total, 4) if total else 0.0
    timeout_rate = round(timeouts / total, 4) if total else 0.0
    average_latency_ms = round(sum(latencies) / len(latencies), 1) if latencies else 0.0

    # Delivery rate: notifications that actually reached a terminal delivered state.
    delivered = session.query(func.count(CommunicationNotification.id)).filter(
        CommunicationNotification.provider == provider,
        CommunicationNotification.status == "delivered",
        CommunicationNotification.created_at >= since,
    ).scalar() or 0
    terminal = session.query(func.count(CommunicationNotification.id)).filter(
        CommunicationNotification.provider == provider,
        CommunicationNotification.status.in_(("delivered", "failed", "rejected", "dead_letter")),
        CommunicationNotification.created_at >= since,
    ).scalar() or 0
    delivery_rate = round(delivered / terminal, 4) if terminal else 1.0

    # Webhook health: processed callbacks vs received callbacks.
    webhook_received = session.query(func.count(CommunicationWebhookEvent.id)).filter(
        CommunicationWebhookEvent.provider == provider,
        CommunicationWebhookEvent.received_at >= since,
    ).scalar() or 0
    webhook_processed = session.query(func.count(CommunicationWebhookEvent.id)).filter(
        CommunicationWebhookEvent.provider == provider,
        CommunicationWebhookEvent.received_at >= since,
        CommunicationWebhookEvent.processing_status == "processed",
    ).scalar() or 0
    webhook_health = round(webhook_processed / webhook_received, 4) if webhook_received else 1.0

    recent_incidents = session.query(func.count(CommunicationIncident.id)).filter(
        CommunicationIncident.opened_at >= since,
        CommunicationIncident.fingerprint.like(f"%{provider}%"),
    ).scalar() or 0
    open_incidents = session.query(func.count(CommunicationIncident.id)).filter(
        CommunicationIncident.status.in_(("open", "investigating")),
        CommunicationIncident.fingerprint.like(f"%{provider}%"),
    ).scalar() or 0

    score = 100.0
    score -= failure_rate * 60
    if success_rate < 0.98:
        score -= (0.98 - success_rate) * 250
    score -= max(0.0, average_latency_ms - 1000) / 1000 * 5
    score -= timeout_rate * 30
    score -= (1 - delivery_rate) * 25
    score -= (1 - webhook_health) * 15
    score -= min(20.0, open_incidents * 10 + recent_incidents * 2)
    score = round(max(0.0, min(100.0, score)), 1)
    if total == 0:
        score = 100.0

    level = _level(score, success_rate if total else 1.0)
    return {
        "provider": provider,
        "score": score,
        "level": level.value,
        "window_hours": hours,
        "attempts": total,
        "success_rate": success_rate,
        "failure_rate": failure_rate,
        "timeout_rate": timeout_rate,
        "delivery_rate": delivery_rate,
        "webhook_health": webhook_health,
        "average_latency_ms": average_latency_ms,
        "recent_incidents": recent_incidents,
        "open_incidents": open_incidents,
        "attempt_status_counts": by_status,
    }


def all_provider_health(session: Session, providers: list[str] | None = None) -> list[dict[str, Any]]:
    names = providers or [row[0] for row in session.query(CommunicationAttempt.provider).distinct().all()]
    snapshots = [provider_health_snapshot(session, name) for name in sorted(set(names))]
    return sorted(snapshots, key=lambda item: item["score"], reverse=True)