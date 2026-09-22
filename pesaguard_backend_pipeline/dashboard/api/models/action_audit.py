"""Compatibility exports for the shared action-audit model."""

from __future__ import annotations

from typing import Any, Mapping, Optional

from pesaguard_backend_pipeline.action_audit import (
    ActionAuditEntry,
    ActionAuditRecord,
    Base,
    build_audit_entry as _build_audit_entry,
)

__all__ = ["ActionAuditEntry", "ActionAuditRecord", "Base", "build_audit_entry"]


def build_audit_entry(
    tenant_id: str,
    actor: str,
    action: str,
    details: Optional[Mapping[str, Any]] = None,
    audit_id: Optional[str] = None,
) -> dict[str, Any]:
    """Factory helper to construct standardized audit entry dictionaries.

    Args:
        tenant_id: Target tenant identifier
        actor: Username, service account, or user ID performing the action
        action: Identifier of the action performed (e.g., 'settings.update', 'webhook.create')
        details: Optional contextual metadata dictionary
        audit_id: Optional explicit audit ID override

    Returns:
        Structured audit dictionary ready for DB insertion or Kafka streaming.
    """
    return _build_audit_entry(
        ActionAuditRecord(
            tenant_id=tenant_id,
            actor=actor,
            action=action,
            details=details,
            id=audit_id,
        )
    )
