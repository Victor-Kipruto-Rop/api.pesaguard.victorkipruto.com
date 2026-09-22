"""Notification policy engine.

Decides channel, provider hints, template, priority, delay, and fallback for
business events. Business services never call providers directly: they publish
events, and this engine turns events into notification decisions using tenant
configuration, customer preferences, quiet hours, risk, and provider health.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from typing import Any, Mapping

from .core.enums import CommunicationChannel, CommunicationPriority
from .domain import is_allowed_now


class RiskClass(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class PolicyDecision:
    channels: tuple[CommunicationChannel, ...]
    priority: CommunicationPriority
    template: str | None = None
    delay_until: datetime | None = None
    fallback_channels: tuple[CommunicationChannel, ...] = ()
    create_incident: bool = False
    quiet_hours_deferred: bool = False
    reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "channels": [channel.value for channel in self.channels],
            "priority": self.priority.value,
            "template": self.template,
            "delay_until": self.delay_until.isoformat() if self.delay_until else None,
            "fallback_channels": [channel.value for channel in self.fallback_channels],
            "create_incident": self.create_incident,
            "quiet_hours_deferred": self.quiet_hours_deferred,
            "reasons": list(self.reasons),
        }


# Default thresholds are tenant-overridable via tenant configuration.
_DEFAULTS: dict[str, Any] = {
    "high_value_threshold": 100_000.0,
    "very_high_value_threshold": 500_000.0,
    "currency": "KES",
    "reconciliation_analyst_max": 1_000.0,
    "reconciliation_manager_max": 100_000.0,
    "fraud_critical_score": 85,
    "fraud_high_score": 60,
    "fraud_medium_score": 35,
    "quiet_hours_start": None,
    "quiet_hours_end": None,
    "quiet_hours_timezone": "Africa/Nairobi",
    "critical_override_quiet_hours": True,
    "channel_costs": {"sms": 0.8, "email": 0.1, "whatsapp": 0.5, "voice": 3.0, "ussd": 0.0},
}


def _env_overrides() -> dict[str, Any]:
    raw = os.getenv("PESAGUARD_COMMUNICATION_POLICY_DEFAULTS", "")
    if not raw:
        return {}
    try:
        loaded = json.loads(raw)
        return loaded if isinstance(loaded, dict) else {}
    except json.JSONDecodeError:
        return {}


def _tenant_defaults(tenant_config: Mapping[str, Any] | None) -> dict[str, Any]:
    merged = dict(_DEFAULTS)
    merged.update(_env_overrides())
    if tenant_config:
        communication = tenant_config.get("communication") if isinstance(tenant_config.get("communication"), dict) else tenant_config
        if isinstance(communication, dict):
            merged.update({key: value for key, value in communication.items() if key in merged or key.startswith("quiet_hours")})
    return merged


def risk_class_for_score(score: float | None, config: Mapping[str, Any]) -> RiskClass:
    if score is None:
        return RiskClass.LOW
    if score >= float(config["fraud_critical_score"]):
        return RiskClass.CRITICAL
    if score >= float(config["fraud_high_score"]):
        return RiskClass.HIGH
    if score >= float(config["fraud_medium_score"]):
        return RiskClass.MEDIUM
    return RiskClass.LOW


def _amount(context: Mapping[str, Any]) -> float | None:
    for key in ("amount", "value", "trans_amount"):
        value = context.get(key)
        if value is None:
            continue
        try:
            return abs(float(value))
        except (TypeError, ValueError):
            continue
    return None


def _reconciliation_escalation(context: Mapping[str, Any], config: Mapping[str, Any]) -> PolicyDecision:
    difference = abs(_amount(context) or 0.0)
    analyst_max = float(config["reconciliation_analyst_max"])
    manager_max = float(config["reconciliation_manager_max"])
    if difference <= analyst_max:
        return PolicyDecision(
            channels=(CommunicationChannel.EMAIL,),
            priority=CommunicationPriority.NORMAL,
            template="reconciliation.analyst_review",
            reasons=("reconciliation_escalation_analyst", f"difference_below_{analyst_max:.0f}"),
        )
    if difference <= manager_max:
        return PolicyDecision(
            channels=(CommunicationChannel.SMS, CommunicationChannel.EMAIL),
            priority=CommunicationPriority.HIGH,
            template="reconciliation.manager_review",
            reasons=("reconciliation_escalation_manager",),
        )
    return PolicyDecision(
        channels=(CommunicationChannel.SMS, CommunicationChannel.EMAIL, CommunicationChannel.VOICE),
        priority=CommunicationPriority.CRITICAL,
        template="reconciliation.executive_review",
        create_incident=True,
        reasons=("reconciliation_escalation_manager_and_executive",),
    )


def _quiet_hours_preference(config: Mapping[str, Any]):
    start, end = config.get("quiet_hours_start"), config.get("quiet_hours_end")
    if not start or not end:
        return None
    from .models import CommunicationPreference

    return CommunicationPreference(
        id="policy-quiet-hours",
        tenant_id="policy",
        recipient="policy",
        quiet_hours_start=str(start),
        quiet_hours_end=str(end),
        timezone=str(config.get("quiet_hours_timezone") or "Africa/Nairobi"),
    )


class NotificationPolicyEngine:
    """Pure decision engine: event + context -> channels/priority/delay/fallback."""

    def __init__(self, *, health_lookup: Mapping[str, float] | None = None, now: datetime | None = None):
        # health_lookup maps channel -> provider health score (0-100); used to
        # order fallback channels by reliability evidence.
        self.health_lookup = dict(health_lookup or {})
        self._now = now

    def _now_utc(self) -> datetime:
        return self._now or datetime.now(timezone.utc)

    def decide(
        self,
        event: str,
        *,
        tenant_id: str,
        tenant_config: Mapping[str, Any] | None = None,
        context: Mapping[str, Any] | None = None,
        customer_preference=None,
    ) -> PolicyDecision:
        config = _tenant_defaults(tenant_config)
        context = dict(context or {})
        handler = getattr(self, f"_decide_{event.replace('.', '_')}", None)
        if handler is None:
            return PolicyDecision((CommunicationChannel.EMAIL,), CommunicationPriority.NORMAL)
        decision = handler(tenant_id, context, config)
        return self._apply_quiet_hours(decision, config, customer_preference)

    def _apply_quiet_hours(self, decision: PolicyDecision, config: Mapping[str, Any], customer_preference) -> PolicyDecision:
        if decision.delay_until is not None:
            return decision
        override_allowed = bool(config.get("critical_override_quiet_hours")) and decision.priority == CommunicationPriority.CRITICAL
        if override_allowed:
            return decision
        preference = customer_preference or _quiet_hours_preference(config)
        if preference is None or is_allowed_now(preference, now=self._now_utc()):
            return decision
        delay = self._quiet_hours_end_delay(preference)
        return PolicyDecision(
            channels=decision.channels,
            priority=decision.priority,
            template=decision.template,
            delay_until=delay,
            fallback_channels=decision.fallback_channels,
            create_incident=decision.create_incident,
            quiet_hours_deferred=True,
            reasons=(*decision.reasons, "deferred_to_quiet_hours_end"),
        )

    def _quiet_hours_end_delay(self, preference) -> datetime:
        tzname = getattr(preference, "timezone", None) or "Africa/Nairobi"
        from zoneinfo import ZoneInfo

        now_local = self._now_utc().astimezone(ZoneInfo(tzname))
        end = str(preference.quiet_hours_end)
        hour, minute = int(end[:2]), int(end[3:5])
        candidate = now_local.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= now_local:
            candidate += timedelta(days=1)
        return candidate.astimezone(timezone.utc)

    # -- individual event policies -------------------------------------------

    def _decide_transaction_completed(self, tenant_id: str, context: Mapping[str, Any], config: Mapping[str, Any]) -> PolicyDecision:
        amount = _amount(context)
        if amount is not None and amount >= float(config["very_high_value_threshold"]):
            return PolicyDecision(
                channels=(CommunicationChannel.SMS, CommunicationChannel.EMAIL, CommunicationChannel.VOICE),
                priority=CommunicationPriority.HIGH,
                template="transaction.high_value_receipt",
                fallback_channels=(CommunicationChannel.EMAIL,),
                reasons=("very_high_value_transaction",),
            )
        if amount is not None and amount >= float(config["high_value_threshold"]):
            return PolicyDecision(
                channels=(CommunicationChannel.SMS, CommunicationChannel.EMAIL, CommunicationChannel.VOICE),
                priority=CommunicationPriority.HIGH,
                template="transaction.high_value_receipt",
                reasons=("high_value_transaction",),
            )
        return PolicyDecision(
            channels=(CommunicationChannel.SMS,),
            priority=CommunicationPriority.NORMAL,
            template="transaction.receipt",
        )

    def _decide_transaction_failed(self, tenant_id: str, context: Mapping[str, Any], config: Mapping[str, Any]) -> PolicyDecision:
        return PolicyDecision(
            channels=(CommunicationChannel.SMS,),
            priority=CommunicationPriority.HIGH,
            template="transaction.failure_notice",
            fallback_channels=(CommunicationChannel.EMAIL,),
            reasons=("transaction_failure_notice",),
        )

    def _decide_transaction_reversed(self, tenant_id: str, context: Mapping[str, Any], config: Mapping[str, Any]) -> PolicyDecision:
        return PolicyDecision(
            channels=(CommunicationChannel.SMS,),
            priority=CommunicationPriority.HIGH,
            template="transaction.reversal_notice",
            fallback_channels=(CommunicationChannel.EMAIL,),
            reasons=("transaction_reversal_notice",),
        )

    def _decide_transaction_suspicious(self, tenant_id: str, context: Mapping[str, Any], config: Mapping[str, Any]) -> PolicyDecision:
        return PolicyDecision(
            channels=(CommunicationChannel.SMS, CommunicationChannel.EMAIL),
            priority=CommunicationPriority.CRITICAL,
            template="transaction.suspicious_alert",
            create_incident=True,
            reasons=("suspicious_transaction_fraud_workflow",),
        )

    def _decide_fraud_suspected(self, tenant_id: str, context: Mapping[str, Any], config: Mapping[str, Any]) -> PolicyDecision:
        risk = risk_class_for_score(context.get("risk_score"), config)
        if risk is RiskClass.CRITICAL:
            return self._decide_fraud_confirmed(tenant_id, context, config)
        return PolicyDecision(
            channels=(CommunicationChannel.EMAIL,),
            priority=CommunicationPriority.HIGH,
            template="fraud.suspected_notice",
            fallback_channels=(CommunicationChannel.SMS,),
            reasons=(f"risk_class_{risk.value.lower()}",),
        )

    def _decide_fraud_confirmed(self, tenant_id: str, context: Mapping[str, Any], config: Mapping[str, Any]) -> PolicyDecision:
        return PolicyDecision(
            channels=(CommunicationChannel.SMS, CommunicationChannel.EMAIL, CommunicationChannel.VOICE),
            priority=CommunicationPriority.CRITICAL,
            template="fraud.confirmed_alert",
            create_incident=True,
            reasons=("fraud_confirmed_critical_workflow",),
        )

    def _decide_fraud_blocked(self, tenant_id: str, context: Mapping[str, Any], config: Mapping[str, Any]) -> PolicyDecision:
        return PolicyDecision(
            channels=(CommunicationChannel.SMS, CommunicationChannel.EMAIL),
            priority=CommunicationPriority.CRITICAL,
            template="fraud.blocked_alert",
            create_incident=True,
            reasons=("fraud_blocked_critical_workflow",),
        )

    def _decide_security_mfa_required(self, tenant_id: str, context: Mapping[str, Any], config: Mapping[str, Any]) -> PolicyDecision:
        return PolicyDecision(
            channels=(CommunicationChannel.SMS,),
            priority=CommunicationPriority.CRITICAL,
            template="security.otp",
            reasons=("security_authentication_immediate",),
        )

    def _decide_reconciliation_exception_created(self, tenant_id: str, context: Mapping[str, Any], config: Mapping[str, Any]) -> PolicyDecision:
        return _reconciliation_escalation(context, config)

    def _decide_transaction_mismatch(self, tenant_id: str, context: Mapping[str, Any], config: Mapping[str, Any]) -> PolicyDecision:
        return _reconciliation_escalation(context, config)

    def _decide_provider_degraded(self, tenant_id: str, context: Mapping[str, Any], config: Mapping[str, Any]) -> PolicyDecision:
        return PolicyDecision(
            channels=(CommunicationChannel.EMAIL,),
            priority=CommunicationPriority.HIGH,
            template="provider.degradation_notice",
            create_incident=True,
            reasons=("provider_degradation_operational",),
        )

    def _decide_provider_failed(self, tenant_id: str, context: Mapping[str, Any], config: Mapping[str, Any]) -> PolicyDecision:
        return PolicyDecision(
            channels=(CommunicationChannel.EMAIL,),
            priority=CommunicationPriority.CRITICAL,
            template="provider.outage_notice",
            create_incident=True,
            reasons=("provider_outage_operational",),
        )