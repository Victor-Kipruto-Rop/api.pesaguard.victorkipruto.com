"""Robust multi-channel alerting service module for PesaGuard discrepancy dispatch."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from models import Discrepancy
from notifier import send_email_alert, send_slack_alert, send_sms_alert

try:
    from metrics import record_alert_delivery
except Exception:  # pragma: no cover - metrics must never break alerting
    def record_alert_delivery(channel: str, success: bool) -> None:  # type: ignore[misc]
        return None

logger = logging.getLogger("pesaguard.alerting.service")


class AlertingService:
    """Manages multi-channel discrepancy alert routing, severity filters, deduplication, and persistence."""

    def __init__(self, session: Optional[Session] = None, tenant_settings: Optional[Dict[str, Any]] = None):
        self.session = session
        self.tenant_settings = tenant_settings or {}
        # In-memory deduplication cache. For horizontal scaling across multiple containers,
        # this should be backed by Redis or a database constraint; kept thread-safe or local here.
        self._alert_ids: set[str] = set()

    def handle_discrepancy(self, discrepancy: Dict[str, Any]) -> Dict[str, Any]:
        """Process an incoming discrepancy notification, route to configured channels, and log outcomes."""
        if not isinstance(discrepancy, dict):
            logger.error("Invalid discrepancy format encountered; expected dictionary, got %s", type(discrepancy))
            return {"status": "failed", "reason": "invalid_discrepancy_format"}

        alert_id = str(discrepancy.get("id") or discrepancy.get("trans_id") or uuid.uuid4())
        
        # Deduplication check
        if alert_id in self._alert_ids:
            logger.info("Duplicate alert suppressed via in-memory deduplication cache: alert_id=%s", alert_id)
            return {"status": "deduped", "alert_id": alert_id, "deliveries": [], "delivery_mode": "deduped"}

        self._alert_ids.add(alert_id)
        
        severity = str(discrepancy.get("severity") or "warning").lower()
        channels = self._resolve_channels(severity)
        locale = self._resolve_locale(discrepancy)
        delivery_mode = self._resolve_delivery_mode(severity, channels)
        deliveries: List[Dict[str, Any]] = []

        if delivery_mode == "digest":
            self._store_delivery_log(alert_id, discrepancy, deliveries)
            logger.info("Discrepancy queued for digest delivery mode: alert_id=%s", alert_id)
            return {"status": "queued", "alert_id": alert_id, "deliveries": deliveries, "delivery_mode": "digest"}

        # Dispatch real-time notifications across resolved channels
        for channel in channels:
            try:
                if channel == "slack":
                    delivered = bool(send_slack_alert(discrepancy, locale=locale))
                elif channel == "sms":
                    delivered = bool(send_sms_alert(discrepancy, locale=locale))
                elif channel == "email":
                    delivered = bool(send_email_alert(discrepancy, locale=locale))
                else:
                    logger.warning("Unrecognized notification channel requested: %s", channel)
                    record_alert_delivery(channel, False)
                    deliveries.append({"channel": channel, "status": "failed", "error": "unsupported_channel"})
                    continue

                record_alert_delivery(channel, delivered)
                deliveries.append({"channel": channel, "status": "sent" if delivered else "failed", "timestamp": datetime.now(timezone.utc).isoformat()})
                if delivered:
                    logger.info("Alert delivered successfully via channel=%s alert_id=%s", channel, alert_id)
                else:
                    logger.warning("Alert delivery reported failure via channel=%s alert_id=%s", channel, alert_id)

            except Exception as exc:
                record_alert_delivery(channel, False)
                logger.exception("Alert delivery failed for channel=%s alert_id=%s: %s", channel, alert_id, exc)
                deliveries.append({"channel": channel, "status": "failed", "error": str(exc)})

        self._store_delivery_log(alert_id, discrepancy, deliveries)
        return {"status": "queued", "alert_id": alert_id, "deliveries": deliveries, "delivery_mode": delivery_mode}

    def _resolve_channels(self, severity: str) -> List[str]:
        """Determine valid notification channels based on severity level and tenant settings."""
        configured = self.tenant_settings.get("alert_channels") or ["slack"]
        if not isinstance(configured, list):
            configured = ["slack"]

        if severity == "critical":
            return [channel for channel in configured if channel in {"slack", "sms", "email"}]
        if severity == "warning":
            return [channel for channel in configured if channel in {"slack", "email"}]
        if severity == "info":
            return [channel for channel in configured if channel == "slack"]
        return []

    def _resolve_delivery_mode(self, severity: str, channels: List[str]) -> str:
        """Determine whether alerts should be dispatched immediately or batched into a digest."""
        if severity == "info":
            return "digest"
        if channels:
            return "realtime"
        return "digest"

    def _resolve_locale(self, discrepancy: Dict[str, Any]) -> str:
        """Resolve localized string preference for templates per tenant/user context."""
        tenant_id = str(discrepancy.get("tenant_id", "default"))
        user_id = discrepancy.get("user_id")

        if hasattr(self.tenant_settings, "resolve_locale") and callable(self.tenant_settings.resolve_locale):
            try:
                return str(self.tenant_settings.resolve_locale(tenant_id, user_id, fallback_locale="en"))
            except Exception as e:
                logger.error("Custom resolve_locale method failed: %s", e)

        if isinstance(self.tenant_settings, dict):
            tenant_cfg = self.tenant_settings.get(tenant_id) or self.tenant_settings.get("default") or {}
            
            if user_id and isinstance(tenant_cfg.get("user_locale_overrides"), dict):
                override = tenant_cfg["user_locale_overrides"].get(user_id) or tenant_cfg["user_locale_overrides"].get(str(user_id))
                if override:
                    return str(override)

            preferred_locale = tenant_cfg.get("preferred_locale") or tenant_cfg.get("default_locale")
            if preferred_locale:
                return str(preferred_locale)

            default_settings = self.tenant_settings.get("default") or {}
            if default_settings.get("preferred_locale"):
                return str(default_settings["preferred_locale"])

        return "en"

    def _store_delivery_log(self, alert_id: str, discrepancy: Dict[str, Any], deliveries: List[Dict[str, Any]]) -> None:
        """Persist alert delivery metrics and event records to the database safely."""
        if self.session is None:
            return

        try:
            trans_id = str(discrepancy.get("trans_id", "unknown"))
            tenant_id = str(discrepancy.get("tenant_id", "default"))
            severity = str(discrepancy.get("severity") or "warning")
            anomaly_type = str(discrepancy.get("status") or discrepancy.get("anomaly_type") or "alert")

            log_entry = Discrepancy(
                id=f"alert-{alert_id}",
                trans_id=trans_id,
                tenant_id=tenant_id,
                anomaly_type=anomaly_type,
                status="alerted",
                severity=severity,
                details=json.dumps({
                    "alert_id": alert_id,
                    "deliveries": deliveries,
                    "discrepancy_payload": discrepancy,
                    "logged_at": datetime.now(timezone.utc).isoformat(),
                }),
                resolved=False,
            )
            self.session.add(log_entry)
            self.session.commit()
            logger.info("Successfully stored delivery audit log for alert_id=%s", alert_id)
        except Exception as exc:
            logger.exception("Failed to store delivery log for alert_id=%s: %s", alert_id, exc)
            if self.session:
                self.session.rollback()
