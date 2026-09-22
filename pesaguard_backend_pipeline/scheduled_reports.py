"""Compatibility entry point for the scheduled report worker."""

from operations.scheduled_reports import (  # noqa: F401
    generate_report_for_tenant,
    get_all_active_tenants,
)

__all__ = ["generate_report_for_tenant", "get_all_active_tenants"]