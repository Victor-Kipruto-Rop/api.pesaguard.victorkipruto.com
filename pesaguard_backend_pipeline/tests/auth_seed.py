"""Shared helper for tests that authenticate against the dashboard API.

``AuthRBAC.authenticate`` (auth_rbac.py) requires a matching, active
``UserAccount`` row for the token's ``user_id``/``tenant_id`` -- a token alone
is no longer enough. Most existing test fixtures only call
``AuthRBAC.generate_token`` and never seed that row, so every request they
make is rejected with 401 before it reaches the endpoint under test. This
seeds the row so a generated token actually authenticates, matching what
``tests/test_dashboard_api.py::test_locale_lookup_rejects_unknown_or_cross_user_ids``
already does by hand.
"""
from __future__ import annotations

from typing import Any, Iterable, Optional


def seed_account(
    session_factory,
    *,
    user_id: str,
    tenant_id: str,
    roles: Iterable[str],
    username: Optional[str] = None,
    permissions: Optional[Iterable[str]] = None,
    status: str = "active",
    authorization_version: int = 1,
) -> None:
    """Insert (or update) the UserAccount row a token for this user/tenant needs.

    Uses ``session.merge`` so it is safe to call more than once for the same
    ``user_id``/``tenant_id`` (e.g. a fixture seeds it and an individual test
    also wants to seed a second, related account).
    """
    from models import UserAccount

    session = session_factory()
    try:
        session.merge(
            UserAccount(
                id=user_id,
                tenant_id=tenant_id,
                username=username or user_id,
                roles=list(roles),
                permissions=list(permissions or []),
                status=status,
                authorization_version=authorization_version,
            )
        )
        session.commit()
    finally:
        session.close()


def seed_account_and_token(session_factory, *, user_id: str, tenant_id: str, roles: Iterable[str], **kwargs: Any) -> str:
    """Seed the account row, then return a matching access token."""
    from auth_rbac import AuthRBAC

    role_list = list(roles)
    seed_account(session_factory, user_id=user_id, tenant_id=tenant_id, roles=role_list, **kwargs)
    return AuthRBAC.generate_token(user_id=user_id, username=user_id, tenant_id=tenant_id, roles=role_list)
