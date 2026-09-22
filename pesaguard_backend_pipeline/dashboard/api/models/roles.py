"""
Role-Based Access Control (RBAC) Module for PesaGuard.

Defines role permissions, permission check guards, and authorization constants
for multi-tenant administrative and financial operations.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

# Canonical Permission Constants
PERM_MANAGE_SETTINGS = "manage:settings"
PERM_VIEW_SETTINGS = "view:settings"
PERM_MANAGE_CONNECTORS = "manage:connectors"
PERM_VIEW_AUDIT_LOG = "view:audit_log"
PERM_RESOLVE_DISCREPANCIES = "resolve:discrepancies"
PERM_VIEW_DISCREPANCIES = "view:discrepancies"
PERM_MANAGE_WEBHOOKS = "manage:webhooks"

ALL_PERMISSIONS: frozenset[str] = frozenset({
    PERM_MANAGE_SETTINGS,
    PERM_VIEW_SETTINGS,
    PERM_MANAGE_CONNECTORS,
    PERM_VIEW_AUDIT_LOG,
    PERM_RESOLVE_DISCREPANCIES,
    PERM_VIEW_DISCREPANCIES,
    PERM_MANAGE_WEBHOOKS,
})


@dataclass(frozen=True)
class RoleDefinition:
    """Immutable role definition mapping a role name to its granted permissions."""
    name: str
    permissions: frozenset[str]

    def __post_init__(self) -> None:
        object.__setattr__(self, "permissions", frozenset(self.permissions))


_ROLES: dict[str, RoleDefinition] = {
    "admin": RoleDefinition(
        "admin",
        frozenset({
            PERM_MANAGE_SETTINGS,
            PERM_VIEW_SETTINGS,
            PERM_MANAGE_CONNECTORS,
            PERM_VIEW_AUDIT_LOG,
            PERM_RESOLVE_DISCREPANCIES,
            PERM_VIEW_DISCREPANCIES,
            PERM_MANAGE_WEBHOOKS,
        }),
    ),
    "finance_officer": RoleDefinition(
        "finance_officer",
        frozenset({
            PERM_VIEW_SETTINGS,
            PERM_RESOLVE_DISCREPANCIES,
            PERM_VIEW_DISCREPANCIES,
            PERM_VIEW_AUDIT_LOG,
        }),
    ),
    "viewer": RoleDefinition(
        "viewer",
        frozenset({
            PERM_VIEW_DISCREPANCIES,
            PERM_VIEW_SETTINGS,
        }),
    ),
    "system": RoleDefinition(
        "system",
        ALL_PERMISSIONS,
    ),
}


def _validate_role_definitions(roles: Mapping[str, RoleDefinition]) -> None:
    for role_name, role_definition in roles.items():
        if role_name != role_definition.name:
            raise ValueError(f"Role key {role_name!r} does not match its definition name")
        if not role_definition.permissions <= ALL_PERMISSIONS:
            raise ValueError(f"Role {role_name!r} contains an unknown permission")


_validate_role_definitions(_ROLES)
ROLES: Mapping[str, RoleDefinition] = MappingProxyType(_ROLES)


def is_valid_role(role: str | None) -> bool:
    """Return whether a role name maps to a configured role."""
    return isinstance(role, str) and role.strip().lower() in ROLES


def has_permission(role: str | None, permission: str) -> bool:
    """Check if a given role possesses a specific permission string.

    Args:
        role: Role name string (e.g. 'admin', 'viewer')
        permission: Permission key to verify

    Returns:
        True if permitted, False otherwise.
    """
    if not isinstance(permission, str):
        return False
    normalized_role = (role or "").strip().lower()
    role_def = ROLES.get(normalized_role)
    return bool(role_def and permission in role_def.permissions)


def enforce_permission(role: str, permission: str, tenant_id: str = "default") -> None:
    """Enforce a role permission check, raising PermissionError if unauthorized.

    This function does not verify that the caller belongs to ``tenant_id``;
    tenant membership and cross-tenant access must be checked by the caller or
    a higher-level authorization service.

    Args:
        role: Active user role
        permission: Required permission
        tenant_id: Target tenant for audit/error context

    Raises:
        PermissionError: If the role lacks the required permission
    """
    if not has_permission(role, permission):
        raise PermissionError(
            f"Access denied for role '{role}' on tenant '{tenant_id}': missing required permission '{permission}'."
        )
