from __future__ import annotations

from typing import Any, Dict, List


class TenantOrgDashboard:
    """Aggregates org, team, department, configuration, and usage data for SaaS reporting."""

    def __init__(self, service):
        self.service = service

    def build_dashboard(self, tenant_id: str, organization_id: str) -> Dict[str, Any]:
        summary = self.service.get_usage_summary(tenant_id, organization_id)
        config = summary.get("config") or {}
        return {
            "tenant_id": tenant_id,
            "organization_id": organization_id,
            "config": config,
            "limits": summary.get("limits") or {},
            "usage": summary.get("usage") or {},
            "health": {
                "status": "healthy",
                "feature_flags": config.get("feature_flags") or {},
            },
        }

    def build_billing_snapshot(self, tenant_id: str, organization_id: str) -> Dict[str, Any]:
        summary = self.service.get_usage_summary(tenant_id, organization_id)
        usage = summary.get("usage") or {}
        totals = {key: float(value.get("current_usage", 0.0)) for key, value in usage.items()}
        return {
            "tenant_id": tenant_id,
            "organization_id": organization_id,
            "usage_totals": totals,
            "currency": "USD",
            "billing_status": "active",
        }
