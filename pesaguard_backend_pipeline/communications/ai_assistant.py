"""AI Operations Assistant for PesaGuard Communications.

Provides natural-language-ready query handlers that answer operational
questions using actual PesaGuard data. Never invents statistics.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import CommunicationAttempt, CommunicationIncident, CommunicationNotification
from ..providers.health import all_provider_health


def answer_delivery_drop(session: Session, *, hours: int = 24) -> dict[str, Any]:
    """Diagnose why SMS delivery may have dropped."""
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    total = session.query(func.count(CommunicationNotification.id)).filter(
        CommunicationNotification.created_at >= since).scalar() or 0
    delivered = session.query(func.count(CommunicationNotification.id)).filter(
        CommunicationNotification.created_at >= since,
        CommunicationNotification.status == "delivered").scalar() or 0
    failed = session.query(func.count(CommunicationNotification.id)).filter(
        CommunicationNotification.created_at >= since,
        CommunicationNotification.status.in_(("failed", "dead_letter"))).scalar() or 0
    rate = (delivered / total * 100) if total else 100.0
    causes = []
    for p in all_provider_health(session):
        if p["score"] < 80:
            causes.append("Provider " + p["provider"] + " health is " + p["level"] + " (score " + str(p["score"]) + ")")
    timeouts = session.query(func.count(CommunicationAttempt.id)).filter(
        CommunicationAttempt.started_at >= since,
        CommunicationAttempt.error_code == "PROVIDER_TIMEOUT").scalar() or 0
    if timeouts > 0:
        causes.append(str(timeouts) + " provider timeouts in the last " + str(hours) + "h")
    return {"question": "Why did SMS delivery drop?", "delivery_rate": round(rate, 1),
            "total_messages": total, "delivered": delivered, "failed": failed,
            "likely_causes": causes or ["Delivery rate within normal parameters"],
            "recommendation": "Monitor provider health" if causes else "No action needed"}


def answer_provider_healthiest(session: Session) -> dict[str, Any]:
    providers = all_provider_health(session)
    if not providers:
        return {"question": "Which provider is healthiest?", "answer": "No provider data available"}
    healthiest = max(providers, key=lambda p: p["score"])
    return {"question": "Which provider is currently healthiest?",
            "healthiest_provider": healthiest["provider"], "score": healthiest["score"],
            "level": healthiest["level"],
            "all_providers": [{"provider": p["provider"], "score": p["score"], "level": p["level"]} for p in providers]}


def answer_cost_this_month(session: Session) -> dict[str, Any]:
    from ..cost import cost_summary
    summary = cost_summary(session)
    return {"question": "How much did communications cost this month?",
            "daily_spend": summary["daily_spend"], "monthly_spend": summary["monthly_spend"],
            "projected_monthly_spend": summary["projected_monthly_spend"],
            "weekly_trend_percent": summary["weekly_trend_percent"], "currency": summary["currency"]}


def answer_tenant_volumes(session: Session, *, limit: int = 10) -> dict[str, Any]:
    since = datetime.now(timezone.utc) - timedelta(days=30)
    rows = (session.query(CommunicationNotification.tenant_id,
            func.count(CommunicationNotification.id).label("message_count"))
            .filter(CommunicationNotification.created_at >= since)
            .group_by(CommunicationNotification.tenant_id)
            .order_by(func.count(CommunicationNotification.id).desc()).limit(limit).all())
    return {"question": "Which tenants generate the most messages?", "period_days": 30,
            "tenants": [{"tenant_id": r[0], "message_count": r[1]} for r in rows]}


def answer_otp_patterns(session: Session) -> dict[str, Any]:
    from ..anomaly import detect_otp_abuse
    findings = detect_otp_abuse(session)
    return {"question": "Are there unusual OTP patterns?", "abuse_detected": len(findings) > 0,
            "findings": findings,
            "summary": str(len(findings)) + " abuse pattern(s) detected" if findings else "OTP patterns are normal"}


def answer_unresolved_incidents(session: Session) -> dict[str, Any]:
    incidents = (session.query(CommunicationIncident)
                 .filter(CommunicationIncident.status.in_(("open", "investigating")))
                 .order_by(CommunicationIncident.last_seen_at.desc()).all())
    return {"question": "Which communication incidents are unresolved?",
            "unresolved_count": len(incidents),
            "incidents": [{"reference": i.reference, "title": i.title, "severity": i.severity,
                          "status": i.status, "occurrence_count": i.occurrence_count} for i in incidents]}