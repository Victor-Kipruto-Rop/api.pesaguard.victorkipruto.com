"""
Role-Based Access Control (RBAC) permission definitions and checkers for PesaGuard.

Provides fine-grained permission evaluation, role hierarchies, and endpoint access control.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, FrozenSet, Optional, Set

logger = logging.getLogger("pesaguard.rbac")

# Comprehensive permission domain definitions
PERM_VIEW_DISCREPANCIES = "view:discrepancies"
PERM_RESOLVE_DISCREPANCIES = "resolve:discrepancies"
PERM_VIEW_CONNECTORS = "view:connectors"
PERM_MANAGE_CONNECTORS = "manage:connectors"
PERM_VIEW_SETTINGS = "view:settings"
PERM_MANAGE_SETTINGS = "manage:settings"
PERM_VIEW_AUDIT_LOG = "view:audit_log"
PERM_MANAGE_WEBHOOKS = "manage:webhooks"
PERM_EXPORT_DATA = "export:data"


@dataclass(frozen=True)
class RoleDefinition:
    """Immutable role definition containing granted permission scopes."""

    name: str
    permissions: FrozenSet[str]


# Pre-defined system role hierarchy
ROLES: Dict[str, RoleDefinition] = {
    "super_admin": RoleDefinition(
        name="super_admin",
        permissions=frozenset({"*"}),  # Full system wildcard access
    ),
    "admin": RoleDefinition(
        name="admin",
        permissions=frozenset({
            "manage:*",
            PERM_VIEW_DISCREPANCIES,
            PERM_RESOLVE_DISCREPANCIES,
            PERM_VIEW_CONNECTORS,
            PERM_MANAGE_CONNECTORS,
            PERM_VIEW_SETTINGS,
            PERM_MANAGE_SETTINGS,
            PERM_VIEW_AUDIT_LOG,
            PERM_MANAGE_WEBHOOKS,
            PERM_EXPORT_DATA,
        }),
    ),
    "operator": RoleDefinition(
        name="operator",
        permissions=frozenset({
            PERM_VIEW_DISCREPANCIES,
            PERM_RESOLVE_DISCREPANCIES,
            PERM_VIEW_CONNECTORS,
            PERM_VIEW_SETTINGS,
            PERM_EXPORT_DATA,
        }),
    ),
    "viewer": RoleDefinition(
        name="viewer",
        permissions=frozenset({
            PERM_VIEW_DISCREPANCIES,
            PERM_VIEW_CONNECTORS,
            PERM_VIEW_SETTINGS,
        }),
    ),
}


def has_permission(role: str, permission: str) -> bool:
    """
    Evaluate if a given role possesses a specific permission or matching wildcard.

    Args:
        role: Role name string (e.g., 'admin', 'operator', 'viewer')
        permission: Specific permission scope (e.g., 'resolve:discrepancies')

    Returns:
        True if authorized, False otherwise.
    """
    if not role or not permission:
        return False

    role_def = ROLES.get(str(role).lower())
    if not role_def:
        return False

    perms = role_def.permissions

    # 1. Global super-admin wildcard match
    if "*" in perms:
        return True

    # 2. Exact permission match
    if permission in perms:
        return True

    # 3. Domain wildcard match (e.g., 'manage:*' grants 'manage:connectors')
    if ":" in permission:
        domain = permission.split(":")[0]
        if f"{domain}:*" in perms:
            return True

    return False


def get_role_permissions(role: str) -> Set[str]:
    """Retrieve all explicit permission strings assigned to a role."""
    role_def = ROLES.get(str(role).lower())
    if not role_def:
        return set()
    return set(role_def.permissions)


def enforce_permission(role: str, permission: str, tenant_id: Optional[str] = None) -> None:
    """
    Enforce permission check, raising a PermissionError if access is denied.

    Raises:
        PermissionError: If role lacks the required permission.
    """
    if not has_permission(role, permission):
        logger.warning(
            "Access denied: role='%s' lacks required permission='%s' (tenant_id=%s)",
            role, permission, tenant_id or "default"
        )
        raise PermissionError(
            f"Role '{role}' is not authorized to perform action '{permission}'."
        )
