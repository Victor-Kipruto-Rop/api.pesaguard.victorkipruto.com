"""Robust alerting consumer module for routing and processing discrepancy events."""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("pesaguard.alerting.consumer")


class AlertingConsumer:
    """Processes discrepancy events from a topic or in-process list and routes them to the alerting service safely."""

    def __init__(
        self,
        alert_service: Any,
        tenant_settings_provider: Optional[Callable[[str], Dict[str, Any]]] = None,
    ):
        self.alert_service = alert_service
        self.tenant_settings_provider = tenant_settings_provider or (lambda _tenant_id: {})

    def process_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process a batch of messages, enriching them with tenant context and routing to alerting."""
        results: List[Dict[str, Any]] = []
        
        if not messages:
            return results

        for message in messages:
            if not isinstance(message, dict):
                logger.error("Invalid message format encountered; expected dictionary, got %s", type(message))
                results.append({"status": "failed", "reason": "invalid_message_format"})
                continue

            trans_id = message.get("trans_id", "unknown")
            tenant_id = str(message.get("tenant_id") or "default")

            try:
                self._apply_tenant_context(message, tenant_id)
                
                # Verify the alert service has the required handling method
                if not hasattr(self.alert_service, "handle_discrepancy"):
                    logger.error("Alert service instance missing 'handle_discrepancy' method")
                    results.append({"status": "failed", "trans_id": trans_id, "reason": "misconfigured_alert_service"})
                    continue

                result = self.alert_service.handle_discrepancy(message)
                results.append(result if isinstance(result, dict) else {"status": "success", "result": result})

            except Exception as e:
                logger.exception("Failed to process alerting message for trans_id=%s tenant_id=%s: %s", trans_id, tenant_id, e)
                results.append({"status": "failed", "trans_id": trans_id, "reason": str(e)})

        return results

    def _apply_tenant_context(self, message: Dict[str, Any], tenant_id: str) -> None:
        """Inject tenant-specific configurations, locales, and fallback channels securely."""
        try:
            settings = self.tenant_settings_provider(tenant_id) or {}
        except Exception as e:
            logger.error("Error retrieving tenant settings for tenant_id=%s: %s", tenant_id, e)
            settings = {}

        if "alert_channels" in settings and "alert_channels" not in message:
            message["alert_channels"] = settings["alert_channels"]
            
        message.setdefault("tenant_id", tenant_id)
        message.setdefault("locale", settings.get("preferred_locale", "en"))
        
        logger.info(
            "Processing discrepancy for alerting",
            extra={
                "tenant_id": tenant_id,
                "trans_id": message.get("trans_id"),
                "locale": message.get("locale"),
            },
        )
