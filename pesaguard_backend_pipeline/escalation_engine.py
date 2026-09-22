"""
Custom escalation rules engine for per-tenant escalation workflows.
Evaluates incident conditions, triggers webhook alerts, and manages operator on-call assignments.
"""

from __future__ import annotations

import hmac
import hashlib
import json
import logging
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Callable

import requests
from webhook_manager import _validate_webhook_url
from sqlalchemy.orm import Session, attributes

from models import EscalationRule, Discrepancy, OnCallRotation
from email_service import EmailService
from tenant_settings import TenantSettingsStore

logger = logging.getLogger("pesaguard.escalation")


def _safe_equals(field: Any, value: Any) -> bool:
    return str(field).lower() == str(value).lower()


def _safe_greater_than(field: Any, value: Any) -> bool:
    try:
        return float(field) > float(value)
    except (ValueError, TypeError):
        return False


def _safe_less_than(field: Any, value: Any) -> bool:
    try:
        return float(field) < float(value)
    except (ValueError, TypeError):
        return False


def _safe_contains(field: Any, value: Any) -> bool:
    return str(value).lower() in str(field).lower()


def _safe_in(field: Any, value: Any) -> bool:
    if isinstance(value, str):
        candidates = [v.strip().lower() for v in value.split(",")]
        return str(field).lower() in candidates
    if isinstance(value, (list, set, tuple)):
        return field in value
    return False


class EscalationEngine:
    """Manages custom escalation rules and executes automated escalations."""

    OPERATORS: Dict[str, Callable[[Any, Any], bool]] = {
        "equals": _safe_equals,
        "not_equals": lambda f, v: not _safe_equals(f, v),
        "greater_than": _safe_greater_than,
        "less_than": _safe_less_than,
        "contains": _safe_contains,
        "in": _safe_in,
    }

    def __init__(self, session: Session):
        self.session = session
        self.email_service = None
        self.settings_store = TenantSettingsStore(os.getenv("TENANT_SETTINGS_FILE", "tenant_settings.json"))

    def create_rule(
        self,
        tenant_id: str,
        name: str,
        description: str,
        condition_field: str,
        condition_operator: str,
        condition_value: str,
        action: str,
        target: Optional[str] = None,
        webhook_url: Optional[str] = None,
        priority: int = 0,
    ) -> Dict[str, Any]:
        """Create a new escalation rule for a tenant."""
        rule_id = f"rule_{uuid.uuid4().hex[:12]}"
        rule = EscalationRule(
            id=rule_id,
            tenant_id=tenant_id,
            name=name,
            description=description,
            condition_field=condition_field,
            condition_operator=condition_operator,
            condition_value=condition_value,
            action=action,
            target=target,
            webhook_url=webhook_url,
            active=True,
            priority=priority,
            created_at=datetime.now(timezone.utc),
        )
        self.session.add(rule)
        self.session.commit()
        logger.info("Created escalation rule_id=%s for tenant_id=%s", rule_id, tenant_id)
        return self._rule_to_dict(rule)

    def get_rules(self, tenant_id: str, active_only: bool = True) -> List[Dict[str, Any]]:
        """Get all escalation rules for a tenant ordered by priority descending."""
        query = self.session.query(EscalationRule).filter(
            EscalationRule.tenant_id == tenant_id
        )
        if active_only:
            query = query.filter(EscalationRule.active == True)
        rules = query.order_by(EscalationRule.priority.desc()).all()
        return [self._rule_to_dict(r) for r in rules]

    def evaluate_and_escalate(
        self,
        tenant_id: str,
        incident: Discrepancy,
    ) -> Dict[str, Any]:
        """Evaluate incident against escalation rules and execute matching escalations."""
        rules = self.get_rules(tenant_id, active_only=True)
        executed_escalations = []

        for rule in rules:
            if self._evaluate_condition(rule, incident):
                escalation_result = self._execute_escalation(rule, incident)
                executed_escalations.append(escalation_result)
                logger.info("Escalated incident_id=%s with rule_id=%s", incident.id, rule["id"])

        return {
            "incident_id": incident.id,
            "escalations_executed": len(executed_escalations),
            "details": executed_escalations,
        }

    def _evaluate_condition(self, rule: Dict[str, Any], incident: Discrepancy) -> bool:
        """Check if incident attributes satisfy the rule condition."""
        field_value = self._get_field_value(rule["condition_field"], incident)
        if field_value is None:
            return False

        operator_func = self.OPERATORS.get(rule["condition_operator"])
        if not operator_func:
            logger.warning("Unrecognized operator '%s' in rule_id=%s", rule["condition_operator"], rule["id"])
            return False

        try:
            return operator_func(field_value, rule["condition_value"])
        except Exception as exc:
            logger.error("Error evaluating condition for rule_id=%s: %s", rule["id"], exc)
            return False

    def _get_field_value(self, field_name: str, incident: Discrepancy) -> Any:
        """Extract evaluation target value from an incident."""
        now = datetime.now(timezone.utc)
        detected = incident.detected_at.replace(tzinfo=timezone.utc) if incident.detected_at and incident.detected_at.tzinfo is None else incident.detected_at

        field_mapping = {
            "severity": incident.severity,
            "anomaly_type": incident.anomaly_type,
            "status": incident.status,
            "age_minutes": ((now - detected).total_seconds() / 60) if detected else 0,
        }
        return field_mapping.get(field_name)

    def _execute_escalation(
        self,
        rule: Dict[str, Any],
        incident: Discrepancy,
    ) -> Dict[str, Any]:
        """Route escalation action execution."""
        action = rule["action"]
        if action == "escalate":
            return self._escalate_to_operator(rule, incident)
        elif action == "notify":
            return self._notify_operator(rule, incident)
        elif action == "webhook":
            return self._trigger_webhook(rule, incident)
        else:
            logger.warning("Unknown escalation action '%s' in rule_id=%s", action, rule["id"])
            return {"status": "unknown_action", "action": action}

    def _escalate_to_operator(
        self,
        rule: Dict[str, Any],
        incident: Discrepancy,
    ) -> Dict[str, Any]:
        """Reassign incident to a target or currently active on-call operator."""
        target_operator = rule.get("target") or self._get_on_call_operator(incident.tenant_id, escalation_level=1)

        if not target_operator:
            target_operator = self._get_on_call_operator(incident.tenant_id, escalation_level=1)

        if target_operator:
            incident.assignee = target_operator
            existing_notes = incident.notes or ""
            incident.notes = f"{existing_notes}\nAuto-escalated by rule: {rule['name']}".strip()

            timeline = list(incident.timeline or [])
            timeline.append({
                "ts": datetime.now(timezone.utc).isoformat(),
                "event": "escalated",
                "rule": rule["name"],
                "assignee": target_operator,
            })
            incident.timeline = timeline
            attributes.flag_modified(incident, "timeline")

            self.session.commit()
            logger.info("Escalated incident_id=%s to operator=%s", incident.id, target_operator)
            return {
                "status": "escalated",
                "assigned_to": target_operator,
                "rule": rule["name"],
            }

        return {"status": "escalation_failed", "reason": "no_operator_available"}

    def _notify_operator(
        self,
        rule: Dict[str, Any],
        incident: Discrepancy,
    ) -> Dict[str, Any]:
        """Dispatch notification email to the assigned or targeted operator."""
        recipient = rule.get("target") or incident.assignee
        if not recipient:
            return {"status": "notification_failed", "reason": "no_recipient"}

        if self.email_service is None:
            self.email_service = EmailService()

        locale = self.settings_store.resolve_locale(incident.tenant_id)
        detected_iso = incident.detected_at.isoformat() if incident.detected_at else None

        self.email_service.send_escalation_notification(
            self.session,
            incident.tenant_id,
            recipient,
            {
                "anomaly_type": incident.anomaly_type,
                "severity": incident.severity,
                "amount": incident.details or "N/A",
                "trans_id": incident.trans_id,
                "detected_at": detected_iso,
            },
            locale=locale,
        )
        return {
            "status": "notification_sent",
            "rule": rule["name"],
            "target": recipient,
        }

    def _trigger_webhook(
        self,
        rule: Dict[str, Any],
        incident: Discrepancy,
    ) -> Dict[str, Any]:
        """Post escalation webhook event payload with HMAC signatures."""
        webhook_url = rule.get("webhook_url")
        if not webhook_url:
            return {"status": "webhook_error", "reason": "no_webhook_url"}
        rejection_reason = _validate_webhook_url(webhook_url)
        if rejection_reason:
            return {"status": "webhook_error", "reason": rejection_reason}

        payload = {
            "event_type": "escalation",
            "incident_id": incident.id,
            "trans_id": incident.trans_id,
            "severity": incident.severity,
            "anomaly_type": incident.anomaly_type,
            "assigned_to": incident.assignee,
            "rule_applied": rule["name"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        body_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
        secret_value = os.getenv("WEBHOOK_SECRET_KEY")
        if not secret_value:
            return {"status": "webhook_error", "reason": "webhook_secret_not_configured"}
        secret = secret_value.encode("utf-8")
        signature = hmac.new(secret, body_bytes, hashlib.sha256).hexdigest()

        headers = {
            "Content-Type": "application/json",
            "X-PesaGuard-Signature": f"sha256={signature}",
            "User-Agent": "PesaGuard-EscalationEngine/2.0",
        }

        try:
            response = requests.post(webhook_url, json=payload, headers=headers, timeout=10, allow_redirects=False)
            return {
                "status": "webhook_triggered",
                "url": webhook_url,
                "rule": rule["name"],
                "response_status": response.status_code,
            }
        except Exception as exc:
            logger.error("Webhook delivery failed for rule '%s' at %s: %s", rule["name"], webhook_url, exc)
            return {"status": "webhook_error", "reason": str(exc)}

    def _get_on_call_operator(
        self,
        tenant_id: str,
        escalation_level: int = 1,
    ) -> Optional[str]:
        """Fetch active on-call operator for tenant, falling back to lower levels if necessary."""
        now = datetime.now(timezone.utc)
        
        for level in range(escalation_level, 4):
            rotation = (
                self.session.query(OnCallRotation)
                .filter(
                    OnCallRotation.tenant_id == tenant_id,
                    OnCallRotation.escalation_level == level,
                    OnCallRotation.shift_start <= now,
                    OnCallRotation.shift_end > now,
                    OnCallRotation.is_active == True,
                )
                .first()
            )
            if rotation and rotation.operator_id:
                return rotation.operator_id

        return None

    def update_rule(self, rule_id: str, **kwargs) -> Dict[str, Any]:
        """Update properties of an existing escalation rule."""
        rule = self.session.query(EscalationRule).filter(EscalationRule.id == rule_id).first()
        if not rule:
            return {"error": "rule_not_found"}

        for key, value in kwargs.items():
            if hasattr(rule, key):
                setattr(rule, key, value)

        self.session.commit()
        logger.info("Updated escalation rule_id=%s", rule_id)
        return self._rule_to_dict(rule)

    def delete_rule(self, rule_id: str) -> Dict[str, Any]:
        """Remove an escalation rule."""
        rule = self.session.query(EscalationRule).filter(EscalationRule.id == rule_id).first()
        if not rule:
            return {"error": "rule_not_found"}

        self.session.delete(rule)
        self.session.commit()
        logger.info("Deleted escalation rule_id=%s", rule_id)
        return {"status": "deleted"}

    def check_webhook_health(self, tenant_id: str, webhook_id: Optional[str] = None) -> Dict[str, Any]:
        """Evaluate recent webhook execution failure rates and trigger health alerts if degraded."""
        from models import WebhookDelivery

        now = datetime.now(timezone.utc)
        check_window = now - timedelta(minutes=30)

        query = self.session.query(WebhookDelivery).filter(WebhookDelivery.created_at >= check_window)
        if webhook_id:
            query = query.filter(WebhookDelivery.webhook_id == webhook_id)

        recent_deliveries = query.all()
        if not recent_deliveries:
            return {"status": "ok", "message": "No recent webhook activity"}

        failed_count = sum(1 for d in recent_deliveries if d.status == "failed")
        failure_rate = failed_count / len(recent_deliveries)
        failure_threshold = float(os.getenv("WEBHOOK_FAILURE_THRESHOLD", "0.10"))

        result = {
            "webhook_id": webhook_id,
            "total_deliveries": len(recent_deliveries),
            "failed_deliveries": failed_count,
            "failure_rate": round(failure_rate, 2),
            "threshold": failure_threshold,
        }

        if failure_rate > failure_threshold:
            result["status"] = "escalation_triggered"
            logger.warning(
                "Webhook failure rate %.1f%% exceeds threshold %.1f%% for tenant_id=%s",
                failure_rate * 100, failure_threshold * 100, tenant_id
            )

            incident = Discrepancy(
                id=f"webhook_health_{webhook_id or 'all'}_{int(now.timestamp())}",
                tenant_id=tenant_id,
                severity="critical" if failure_rate > 0.5 else "warning",
                anomaly_type="webhook_delivery_failure",
                status="needs_review",
                details=json.dumps(result),
                detected_at=now,
                timeline=[{"ts": now.isoformat(), "event": "webhook_health_failure"}],
            )

            webhook_health_rules = self.session.query(EscalationRule).filter(
                EscalationRule.tenant_id == tenant_id,
                EscalationRule.condition_field == "anomaly_type",
                EscalationRule.condition_value == "webhook_delivery_failure",
                EscalationRule.active == True,
            ).all()

            escalations = [self._execute_escalation(r, incident) for r in webhook_health_rules]
            result["escalations"] = escalations
        else:
            result["status"] = "ok"

        return result

    def check_queue_backlog(self, tenant_id: str) -> Dict[str, Any]:
        """Monitor event processing queues and escalate if backlog thresholds are exceeded."""
        from models import DeadLetter

        now = datetime.now(timezone.utc)
        check_window = now - timedelta(minutes=5)

        dead_letter_count = self.session.query(DeadLetter).filter(
            DeadLetter.tenant_id == tenant_id,
            DeadLetter.created_at >= check_window,
        ).count()

        backlog_threshold = int(os.getenv("QUEUE_BACKLOG_THRESHOLD", "1000"))

        result = {
            "tenant_id": tenant_id,
            "dead_letters_unprocessed": dead_letter_count,
            "threshold": backlog_threshold,
            "check_window_minutes": 5,
        }

        if dead_letter_count > backlog_threshold:
            result["status"] = "escalation_triggered"
            logger.warning(
                "Queue backlog detected: %d unprocessed dead letters exceed threshold %d",
                dead_letter_count, backlog_threshold
            )

            incident = Discrepancy(
                id=f"queue_backlog_{int(now.timestamp())}",
                tenant_id=tenant_id,
                severity="critical" if dead_letter_count > backlog_threshold * 2 else "warning",
                anomaly_type="queue_backlog",
                status="needs_review",
                details=json.dumps(result),
                detected_at=now,
                timeline=[{"ts": now.isoformat(), "event": "queue_backlog_exceeded"}],
            )

            backlog_rules = self.session.query(EscalationRule).filter(
                EscalationRule.tenant_id == tenant_id,
                EscalationRule.condition_field == "anomaly_type",
                EscalationRule.condition_value == "queue_backlog",
                EscalationRule.active == True,
            ).all()

            escalations = [self._execute_escalation(r, incident) for r in backlog_rules]
            result["escalations"] = escalations
        else:
            result["status"] = "ok"

        return result

    def _rule_to_dict(self, rule: EscalationRule) -> Dict[str, Any]:
        """Convert EscalationRule ORM entity to dictionary payload."""
        return {
            "id": rule.id,
            "tenant_id": rule.tenant_id,
            "name": rule.name,
            "description": rule.description,
            "condition_field": rule.condition_field,
            "condition_operator": rule.condition_operator,
            "condition_value": rule.condition_value,
            "action": rule.action,
            "target": rule.target,
            "webhook_url": rule.webhook_url,
            "active": rule.active,
            "priority": rule.priority,
            "created_at": rule.created_at.isoformat() if rule.created_at else None,
        }
