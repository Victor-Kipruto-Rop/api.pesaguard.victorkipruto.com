import pytest

from dashboard.api.models.roles import (
    ALL_PERMISSIONS,
    PERM_MANAGE_CONNECTORS,
    PERM_MANAGE_SETTINGS,
    ROLES,
    enforce_permission,
    has_permission,
    is_valid_role,
)


def test_permissions_are_immutable():
    assert isinstance(ALL_PERMISSIONS, frozenset)
    with pytest.raises(AttributeError):
        ROLES["admin"].permissions.add("unexpected:permission")


def test_role_lookup_normalizes_names_and_denies_unknown_roles():
    assert has_permission(" ADMIN ", PERM_MANAGE_SETTINGS)
    assert not has_permission("viewer", PERM_MANAGE_CONNECTORS)
    assert not has_permission("unknown", PERM_MANAGE_SETTINGS)
    assert not has_permission(None, PERM_MANAGE_SETTINGS)
    assert is_valid_role(" ADMIN ")
    assert not is_valid_role("unknown")


def test_enforce_permission_includes_tenant_context():
    with pytest.raises(PermissionError, match="tenant-b"):
        enforce_permission("viewer", PERM_MANAGE_CONNECTORS, tenant_id="tenant-b")
