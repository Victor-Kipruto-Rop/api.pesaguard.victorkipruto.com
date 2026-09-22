"""Enterprise-grade Authentication and Role-Based Access Control (RBAC) for PesaGuard API.

Role Hierarchy (from most to least privileged):
  1. admin: Full access to all features (settings, users, escalation rules, webhooks)
  2. operator: Read/write discrepancies, view analytics, perform bulk operations
  3. customer-user: Read-only access to discrepancies and analytics (customer portal)
  4. read-only: Read-only viewer access (minimal permissions)

Token Expiry: Configurable via TOKEN_EXPIRY_HOURS (default 24h)
Auth Required: Default on; controlled via PESAGUARD_API_AUTH_REQUIRED
"""

from __future__ import annotations

from environment import required_env

import logging
import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from functools import wraps
from threading import Lock
from typing import Any, Dict, List, Optional

import jwt
from flask import g, jsonify, request
from sqlalchemy import Boolean, Column, DateTime, String, Text, create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

logger = logging.getLogger("pesaguard.auth_rbac")


def _record_security_event() -> None:
    try:
        from metrics import record_security_event
        record_security_event()
    except Exception:
        logger.debug("Unable to record authentication security metric", exc_info=True)

_INSECURE_DEV_SECRET = "pesaguard-secret-key-change-in-prod"


def _parse_token_expiry_hours() -> int:
    raw_value = os.getenv("PESAGUARD_TOKEN_EXPIRY_HOURS", "24")
    try:
        value = int(raw_value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("PESAGUARD_TOKEN_EXPIRY_HOURS must be an integer from 1 to 168.") from exc
    if not 1 <= value <= 168:
        raise RuntimeError("PESAGUARD_TOKEN_EXPIRY_HOURS must be an integer from 1 to 168.")
    return value

SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not SECRET_KEY:
    if (
        os.getenv("PESAGUARD_ALLOW_INSECURE_DEV_SECRET") == "1"
        and os.getenv("FLASK_ENV", os.getenv("ENVIRONMENT", "development")).lower() not in {"production", "prod"}
    ):
        SECRET_KEY = _INSECURE_DEV_SECRET
        logger.warning(
            "JWT_SECRET_KEY is not set â€” using an insecure dev secret because "
            "PESAGUARD_ALLOW_INSECURE_DEV_SECRET=1. Never use this in production."
        )
    else:
        raise RuntimeError(
            "JWT_SECRET_KEY environment variable is required and was not set. "
            "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\" "
            "and set it as JWT_SECRET_KEY."
        )
if len(SECRET_KEY.encode("utf-8")) < 32:
    raise RuntimeError("JWT_SECRET_KEY must contain at least 32 bytes.")

ALGORITHM = "HS256"
TOKEN_EXPIRY_HOURS = _parse_token_expiry_hours()
JWT_ISSUER = os.getenv("JWT_ISSUER", "pesaguard")
JWT_AUDIENCE = os.getenv("JWT_AUDIENCE", "pesaguard-api")
TENANT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
JWT_LEEWAY_SECONDS = 30
JWT_ACTIVE_KID = os.getenv("JWT_ACTIVE_KID", "current")
try:
    _configured_keys = json.loads(os.getenv("JWT_KEYS_JSON", "{}"))
except json.JSONDecodeError as exc:
    raise RuntimeError("JWT_KEYS_JSON must be a JSON object mapping key IDs to secrets.") from exc
if not isinstance(_configured_keys, dict) or any(not isinstance(kid, str) or not isinstance(secret, str) for kid, secret in _configured_keys.items()):
    raise RuntimeError("JWT_KEYS_JSON must be a JSON object mapping key IDs to secrets.")
JWT_KEYS = dict(_configured_keys) or {JWT_ACTIVE_KID: SECRET_KEY}
if JWT_ACTIVE_KID not in JWT_KEYS:
    raise RuntimeError("JWT_ACTIVE_KID must identify a configured JWT signing key.")
if any(len(secret.encode("utf-8")) < 32 for secret in JWT_KEYS.values()):
    raise RuntimeError("All configured JWT signing keys must contain at least 32 bytes.")
_JWT_REQUIRED_CLAIMS = ["exp", "iat", "jti", "user_id", "username", "tenant_id", "type", "iss", "aud", "auth_version"]


class AuthenticationUnavailable(RuntimeError):
    """Raised when authentication state cannot be verified safely."""


def _valid_tenant_id(value: Any) -> bool:
    return isinstance(value, str) and bool(TENANT_ID_PATTERN.fullmatch(value))


def parse_bearer_token(header: str) -> Optional[str]:
    """Parse one bearer token using the same rules across middleware layers."""
    parts = header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        return None
    return parts[1]


def _sanitize_revocation_reason(reason: Optional[str]) -> Optional[str]:
    if reason is None:
        return None
    if not isinstance(reason, str):
        raise ValueError("Revocation reason must be a string.")
    sanitized = "".join(char for char in reason if char in "\t\n" or ord(char) >= 32)
    return sanitized[:512]


def _jwt_signing_key() -> str:
    return JWT_KEYS[JWT_ACTIVE_KID]


def _jwt_verification_key(token: str) -> str:
    try:
        header = jwt.get_unverified_header(token)
    except jwt.InvalidTokenError:
        raise
    kid = header.get("kid", JWT_ACTIVE_KID)
    key = JWT_KEYS.get(kid)
    if not key:
        raise jwt.InvalidTokenError("Unknown JWT key ID")
    return key


def _session_is_active(session_id: Optional[str], user_id: str, tenant_id: str) -> bool:
    if not session_id:
        return True
    if not isinstance(session_id, str):
        return False
    _ensure_revocation_store_ready()
    session = _RevocationSession()
    try:
        row = session.execute(
            text("SELECT active FROM user_sessions WHERE id = :session_id AND user_id = :user_id AND tenant_id = :tenant_id"),
            {"session_id": session_id, "user_id": user_id, "tenant_id": tenant_id},
        ).first()
        return bool(row and row[0])
    except Exception as exc:
        session.rollback()
        raise AuthenticationUnavailable("Session state is unavailable") from exc
    finally:
        session.close()


def _account_authorization_version(user_id: str, tenant_id: str) -> int:
    _ensure_revocation_store_ready()
    session = _RevocationSession()
    try:
        row = session.execute(
            text("SELECT authorization_version FROM user_accounts WHERE id = :user_id AND tenant_id = :tenant_id"),
            {"user_id": user_id, "tenant_id": tenant_id},
        ).first()
        return int(row[0]) if row else 1
    except Exception as exc:
        session.rollback()
        raise AuthenticationUnavailable("Account authorization state is unavailable") from exc
    finally:
        session.close()


def _account_is_active_and_current(user_id: str, tenant_id: str, authorization_version: Any) -> bool:
    _ensure_revocation_store_ready()
    session = _RevocationSession()
    try:
        row = session.execute(
            text("SELECT status, authorization_version FROM user_accounts WHERE id = :user_id AND tenant_id = :tenant_id"),
            {"user_id": user_id, "tenant_id": tenant_id},
        ).first()
        if row is None:
            return False
        return row[0] == "active" and int(row[1]) == authorization_version
    except Exception as exc:
        session.rollback()
        raise AuthenticationUnavailable("Account authorization state is unavailable") from exc
    finally:
        session.close()


def auth_required() -> bool:
    """Allow auth bypass only outside production deployments."""
    environment = os.getenv("FLASK_ENV", os.getenv("ENVIRONMENT", "development")).lower()
    if environment in {"production", "prod"}:
        return True
    return os.getenv("PESAGUARD_API_AUTH_REQUIRED", "1") == "1"


def assert_auth_configuration() -> None:
    """Reject an explicitly disabled API auth policy in production."""
    environment = os.getenv("FLASK_ENV", os.getenv("ENVIRONMENT", "development")).lower()
    if environment in {"production", "prod"} and os.getenv("PESAGUARD_API_AUTH_REQUIRED", "1") != "1":
        raise RuntimeError("PESAGUARD_API_AUTH_REQUIRED must be enabled in production")

# ----------------------------------------------------------------------------
# Distributed Database Token Revocation Store
# ----------------------------------------------------------------------------
_RevocationBase = declarative_base()


class RevokedToken(_RevocationBase):
    __tablename__ = "revoked_tokens"

    jti = Column(String, primary_key=True)
    revoked_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    reason = Column(Text, nullable=True)


class RefreshTokenRecord(_RevocationBase):
    """Persisted refresh-token state used for rotation and reuse detection."""

    __tablename__ = "refresh_token_records"

    jti = Column(String, primary_key=True)
    token_hash = Column(String, nullable=False, unique=True, index=True)
    family_id = Column(String, nullable=False, index=True)
    user_id = Column(String, nullable=False)
    username = Column(String, nullable=False)
    tenant_id = Column(String, nullable=False)
    session_id = Column(String, nullable=True)
    device_id = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    ip_address = Column(String, nullable=True)
    issued_at = Column(DateTime(timezone=True), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    family_revoked = Column(Boolean, nullable=False, default=False)


_revocation_engine = None
_RevocationSession = None
_revocation_init_lock = Lock()
_revocation_store_checked = False


def configure_revocation_store(engine, session_factory) -> None:
    """Bind authentication state to the application's primary database session."""
    global _revocation_engine, _RevocationSession, _revocation_store_checked
    with _revocation_init_lock:
        _revocation_engine = engine
        _RevocationSession = session_factory
        _revocation_store_checked = False


def _ensure_revocation_store_ready() -> None:
    """Initialize the revocation store only after its migration has run."""
    global _revocation_engine, _RevocationSession, _revocation_store_checked
    if _RevocationSession is not None and _revocation_store_checked:
        return

    with _revocation_init_lock:
        if _RevocationSession is not None and _revocation_store_checked:
            return
        try:
            if _RevocationSession is None:
                database_url = required_env("DATABASE_URL")
                if database_url.startswith("sqlite"):
                    engine_kwargs = {"connect_args": {"check_same_thread": False}}
                    if database_url in {"sqlite://", "sqlite:///:memory:"}:
                        engine_kwargs["poolclass"] = StaticPool
                    engine = create_engine(database_url, **engine_kwargs)
                else:
                    engine = create_engine(
                        database_url,
                        pool_pre_ping=True,
                        pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
                        max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "10")),
                    )
                try:
                    from metrics import instrument_engine_query_timing
                    instrument_engine_query_timing(engine)
                except Exception:
                    logger.debug("Revocation store engine query timing instrumentation skipped.", exc_info=True)
                _revocation_engine = engine
                _RevocationSession = sessionmaker(bind=engine, expire_on_commit=False)
            engine = _revocation_engine
            required_tables = {"revoked_tokens", "refresh_token_records", "user_accounts"}
            missing_tables = {
                table_name for table_name in required_tables
                if not inspect(engine).has_table(table_name)
            }
            if missing_tables:
                raise RuntimeError(
                    "Required authentication tables are missing; run database migrations: "
                    + ", ".join(sorted(missing_tables))
                )
            _revocation_store_checked = True
        except Exception as exc:
            raise AuthenticationUnavailable("Authentication state is unavailable") from exc


class User:
    """Represents an authenticated user principal with roles and computed permissions."""

    def __init__(
        self,
        user_id: str,
        username: str,
        tenant_id: str,
        roles: List[str],
        permissions: List[str],
    ):
        self.user_id = user_id
        self.username = username
        self.tenant_id = tenant_id
        self.roles = roles
        self.permissions = permissions


class IdentityAccessService:
    """Simple identity-factory used by external IdP integrations and policy enforcement."""

    @staticmethod
    def create_principal(
        user_id: str,
        username: str,
        tenant_id: str,
        roles: Optional[List[str]] = None,
        permissions: Optional[List[str]] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> User:
        normalized_roles = []
        for role in (roles or []):
            if not isinstance(role, str):
                raise ValueError("Roles must contain only strings.")
            normalized = AuthRBAC.normalize_role_name(role)
            if normalized is None:
                raise ValueError(f"Unknown role: {role}")
            if normalized not in normalized_roles:
                normalized_roles.append(normalized)
        if not normalized_roles:
            normalized_roles = ["read-only"]

        role_permissions = set(AuthRBAC._get_permissions_for_roles(normalized_roles))
        if permissions is None:
            trusted_permissions = sorted(role_permissions)
        else:
            if not isinstance(permissions, list) or not all(isinstance(permission, str) for permission in permissions):
                raise ValueError("Permissions must be a list of permission strings.")
            trusted_permissions = sorted(role_permissions.intersection(set(permissions)))

        return User(
            user_id=user_id,
            username=username,
            tenant_id=tenant_id,
            roles=normalized_roles,
            permissions=trusted_permissions,
        )


class AuthRBAC:
    """Authentication, JWT lifecycle, and Role-Based Access Control manager."""

    ROLE_PERMISSIONS: Dict[str, List[str]] = {
        "owner": [
            "read:discrepancies",
            "write:discrepancies",
            "delete:discrepancies",
            "read:analytics",
            "write:escalation_rules",
            "read:settings",
            "write:settings",
            "manage:webhooks",
            "manage:users",
            "manage:on_call",
            "manage:settings",
            "manage:organizations",
            "manage:teams",
            "manage:departments",
            "manage:billing",
            "manage:providers",
            "read:providers",
            "read:usage",
            "bulk:operations",
            "read:metrics",
            "send:communications",
            "read:communications",
            "export:communications",
            "manage:api_keys",
            "manage:mfa",
            "manage:all_tenants",
            "manage:tenant_isolation",
            "manage:security",
        ],
        "admin": [
            "read:discrepancies",
            "write:discrepancies",
            "delete:discrepancies",
            "read:analytics",
            "write:escalation_rules",
            "read:settings",
            "write:settings",
            "manage:webhooks",
            "manage:users",
            "manage:on_call",
            "manage:settings",
            "manage:organizations",
            "manage:teams",
            "manage:departments",
            "manage:billing",
            "manage:providers",
            "read:providers",
            "read:usage",
            "bulk:operations",
            "read:metrics",
            "send:communications",
            "read:communications",
            "export:communications",
            "manage:api_keys",
            "manage:mfa",
        ],
        "finance": [
            "read:discrepancies",
            "read:analytics",
            "read:settings",
            "read:providers",
            "read:usage",
            "read:metrics",
            "export:communications",
            "read:reports",
            "read:transactions",
            "read:revenue",
        ],
        "operations": [
            "read:discrepancies",
            "write:discrepancies",
            "read:analytics",
            "read:settings",
            "read:providers",
            "read:usage",
            "bulk:operations",
            "read:metrics",
            "read:transactions",
        ],
        "analyst": [
            "read:discrepancies",
            "read:analytics",
            "read:settings",
            "read:providers",
            "read:usage",
            "read:metrics",
            "read:reports",
            "read:transactions",
        ],
        "auditor": [
            "read:discrepancies",
            "read:analytics",
            "read:settings",
            "read:providers",
            "read:usage",
            "read:metrics",
            "read:reports",
            "read:transactions",
            "read:audit_logs",
            "read:revenue",
        ],
        "read-only": [
            "read:discrepancies",
            "read:analytics",
            "read:providers",
            "read:usage",
        ],
        "platform-admin": [
            "read:discrepancies",
            "write:discrepancies",
            "delete:discrepancies",
            "read:analytics",
            "write:escalation_rules",
            "read:settings",
            "write:settings",
            "manage:webhooks",
            "manage:users",
            "manage:on_call",
            "manage:settings",
            "manage:organizations",
            "manage:teams",
            "manage:departments",
            "manage:billing",
            "manage:providers",
            "read:providers",
            "read:usage",
            "bulk:operations",
            "read:metrics",
            "send:communications",
            "read:communications",
            "export:communications",
            "manage:api_keys",
            "manage:mfa",
            "manage:all_tenants",
        ],
        "operator": [
            "read:discrepancies",
            "write:discrepancies",
            "read:analytics",
            "read:providers",
            "read:settings",
            "manage:teams",
            "manage:departments",
            "read:usage",
            "bulk:operations",
            "read:metrics",
        ],
        "customer-user": [
            "read:discrepancies",
            "read:analytics",
            "read:providers",
            "read:settings",
            "read:usage",
        ],
        "org-admin": [
            "manage:organizations",
            "manage:teams",
            "manage:departments",
            "manage:billing",
            "read:usage",
            "read:settings",
            "write:settings",
        ],
        "org-manager": [
            "manage:teams",
            "manage:departments",
            "read:usage",
            "read:settings",
        ],
        "department-admin": [
            "manage:departments",
            "read:usage",
            "read:settings",
        ],
    }

    @classmethod
    def normalize_role_name(cls, role: Optional[str]) -> Optional[str]:
        """Canonicalize names like "Customer User" or "customer-user" into internal names."""
        if role is None:
            return None
        normalized = str(role).strip().lower().replace(" ", "-").replace("_", "-")
        normalized = normalized.replace("/", "-")
        if normalized in {"customer-user", "customer_user"}:
            return "customer-user"
        if normalized in {"read-only", "read_only"}:
            return "read-only"
        if normalized in {"customeruser"}:
            return "customer-user"
        if normalized in {"org-admin", "org_admin"}:
            return "org-admin"
        if normalized in {"org-manager", "org_manager"}:
            return "org-manager"
        if normalized in {"department-admin", "department_admin"}:
            return "department-admin"
        if normalized in {"admin", "platform-admin", "operator", "read-only", "customer-user", "org-admin", "org-manager", "department-admin"}:
            return normalized
        return normalized if normalized in cls.ROLE_PERMISSIONS else None

    @classmethod
    def _normalize_roles_for_token(cls, roles: List[str]) -> List[str]:
        if not isinstance(roles, list) or not roles:
            raise ValueError("Roles must be a non-empty list.")
        normalized_roles = []
        for role in roles:
            if not isinstance(role, str):
                raise ValueError("Roles must contain only strings.")
            normalized = cls.normalize_role_name(role)
            if normalized is None:
                raise ValueError(f"Unknown role: {role}")
            if normalized not in normalized_roles:
                normalized_roles.append(normalized)
        return normalized_roles

    @classmethod
    def generate_token(
        cls,
        user_id: str,
        username: str,
        tenant_id: str,
        roles: List[str],
        session_id: Optional[str] = None,
    ) -> str:
        """Generate a signed JWT token containing claims, unique JTI, and permissions."""
        if not _valid_tenant_id(tenant_id):
            raise ValueError("tenant_id must match the configured tenant ID format.")
        authorization_version = _account_authorization_version(user_id, tenant_id)
        normalized_roles = cls._normalize_roles_for_token(roles)
        permissions = cls._get_permissions_for_roles(normalized_roles)
        now = datetime.now(timezone.utc)
        payload = {
            "type": "access",
            "iss": JWT_ISSUER,
            "aud": JWT_AUDIENCE,
            "auth_version": authorization_version,
            "user_id": user_id,
            "username": username,
            "tenant_id": tenant_id,
            "roles": normalized_roles,
            "permissions": permissions,
            "jti": str(uuid.uuid4()),
            "iat": now,
            "exp": now + timedelta(hours=TOKEN_EXPIRY_HOURS),
        }
        if session_id:
            payload["session_id"] = str(session_id)
        return jwt.encode(payload, _jwt_signing_key(), algorithm=ALGORITHM, headers={"kid": JWT_ACTIVE_KID})

    @classmethod
    def generate_refresh_token(
        cls,
        user_id: str,
        username: str,
        tenant_id: str,
        roles: List[str],
        session_id: Optional[str] = None,
        family_id: Optional[str] = None,
        device_id: Optional[str] = None,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> str:
        """Generate and persist a refresh token in a revocable token family."""
        if not _valid_tenant_id(tenant_id):
            raise ValueError("tenant_id must match the configured tenant ID format.")
        authorization_version = _account_authorization_version(user_id, tenant_id)
        normalized_roles = cls._normalize_roles_for_token(roles)
        permissions = cls._get_permissions_for_roles(normalized_roles)
        now = datetime.now(timezone.utc)
        token_jti = str(uuid.uuid4())
        token_family_id = family_id or str(uuid.uuid4())
        expires_at = now + timedelta(days=30)
        payload = {
            "type": "refresh",
            "iss": JWT_ISSUER,
            "aud": JWT_AUDIENCE,
            "auth_version": authorization_version,
            "user_id": user_id,
            "username": username,
            "tenant_id": tenant_id,
            "roles": normalized_roles,
            "permissions": permissions,
            "jti": token_jti,
            "family_id": token_family_id,
            "iat": now,
            "exp": expires_at,
        }
        if session_id:
            payload["session_id"] = str(session_id)
        if device_id:
            payload["device_id"] = str(device_id)
        token = jwt.encode(payload, _jwt_signing_key(), algorithm=ALGORITHM, headers={"kid": JWT_ACTIVE_KID})
        _ensure_revocation_store_ready()
        session = _RevocationSession()
        try:
            session.add(RefreshTokenRecord(
                jti=token_jti,
                token_hash=cls._hash_refresh_token(token),
                family_id=token_family_id,
                user_id=user_id,
                username=username,
                tenant_id=tenant_id,
                session_id=str(session_id) if session_id else None,
                device_id=str(device_id) if device_id else None,
                user_agent=user_agent,
                ip_address=ip_address,
                issued_at=now,
                expires_at=expires_at,
            ))
            session.commit()
        except Exception:
            session.rollback()
            logger.exception("Failed to persist refresh token state for JTI %s", token_jti)
            raise
        finally:
            session.close()
        return token

    @staticmethod
    def _hash_refresh_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @classmethod
    def verify_token(cls, token: str) -> Optional[User]:
        """Verify JWT signature, expiry, and revocation state to return a User principal."""
        try:
            payload = jwt.decode(
                token,
                _jwt_verification_key(token),
                algorithms=[ALGORITHM],
                issuer=JWT_ISSUER,
                audience=JWT_AUDIENCE,
                leeway=JWT_LEEWAY_SECONDS,
                options={"require": _JWT_REQUIRED_CLAIMS},
            )
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            return None

        if payload.get("type", "access") != "access":
            return None

        jti = payload.get("jti")
        if not isinstance(jti, str) or not jti.strip():
            return None
        if cls.is_token_revoked(jti):
            logger.warning("Attempted authentication with revoked JTI: %s", jti)
            return None

        try:
            user_id = payload["user_id"]
            username = payload["username"]
            tenant_id = payload["tenant_id"]
        except KeyError as exc:
            logger.warning("JWT payload missing mandatory claim: %s", exc)
            return None

        if not isinstance(user_id, str) or not user_id.strip():
            logger.warning("JWT payload has invalid user_id claim")
            return None
        if not isinstance(username, str) or not username.strip():
            logger.warning("JWT payload has invalid username claim")
            return None
        if not _valid_tenant_id(tenant_id):
            logger.warning("JWT payload has invalid tenant_id claim")
            return None
        if not _session_is_active(payload.get("session_id"), user_id, tenant_id):
            logger.warning("JWT payload references an inactive or unknown session")
            return None
        if not _account_is_active_and_current(user_id, tenant_id, payload.get("auth_version")):
            logger.warning("JWT payload references a disabled or stale account")
            return None

        roles = payload.get("roles")
        if not isinstance(roles, list) or not all(isinstance(role, str) for role in roles):
            logger.warning("JWT payload has invalid roles claim")
            return None

        normalized_roles: List[str] = []
        for role in roles:
            normalized = cls.normalize_role_name(role)
            if normalized not in cls.ROLE_PERMISSIONS:
                logger.warning("JWT payload contains unknown role")
                return None
            if normalized not in normalized_roles:
                normalized_roles.append(normalized)

        if not normalized_roles:
            logger.warning("JWT payload contains no valid roles")
            return None

        permissions_claim = payload.get("permissions")
        if permissions_claim is not None and (not isinstance(permissions_claim, list) or not all(isinstance(permission, str) for permission in permissions_claim)):
            logger.warning("JWT payload has invalid permissions claim")
            return None

        trusted_permissions = cls._get_permissions_for_roles(normalized_roles)
        if permissions_claim is not None and any(permission not in trusted_permissions for permission in permissions_claim):
            logger.warning("JWT payload contains permissions not consistent with confirmed roles for user %s", user_id)
            return None

        return User(
            user_id=user_id,
            username=username,
            tenant_id=tenant_id,
            roles=normalized_roles,
            permissions=trusted_permissions,
        )

    @classmethod
    def verify_refresh_token(cls, token: str) -> Optional[User]:
        """Verify a refresh JWT and require an active persisted token record."""
        try:
            payload = jwt.decode(
                token,
                _jwt_verification_key(token),
                algorithms=[ALGORITHM],
                issuer=JWT_ISSUER,
                audience=JWT_AUDIENCE,
                leeway=JWT_LEEWAY_SECONDS,
                options={"require": _JWT_REQUIRED_CLAIMS},
            )
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            return None

        if payload.get("type", "access") != "refresh":
            return None

        jti = payload.get("jti")
        family_id = payload.get("family_id")
        if not isinstance(jti, str) or not jti.strip() or not isinstance(family_id, str):
            return None
        _ensure_revocation_store_ready()
        session = _RevocationSession()
        try:
            record = session.get(RefreshTokenRecord, jti)
            if (
                record is None
                or record.token_hash != cls._hash_refresh_token(token)
                or record.family_id != family_id
                or record.used_at is not None
                or record.revoked_at is not None
                or record.family_revoked
            ):
                return None
        finally:
            session.close()

        if cls.is_token_revoked(jti):
            logger.warning("Attempted authentication with revoked JTI: %s", jti)
            return None

        try:
            user_id = payload["user_id"]
            username = payload["username"]
            tenant_id = payload["tenant_id"]
        except KeyError as exc:
            logger.warning("JWT payload missing mandatory claim: %s", exc)
            return None

        if not isinstance(user_id, str) or not user_id.strip():
            logger.warning("JWT payload has invalid user_id claim")
            return None
        if not isinstance(username, str) or not username.strip():
            logger.warning("JWT payload has invalid username claim")
            return None
        if not _valid_tenant_id(tenant_id):
            logger.warning("JWT payload has invalid tenant_id claim")
            return None
        if not _session_is_active(payload.get("session_id"), user_id, tenant_id):
            logger.warning("JWT payload references an inactive or unknown session")
            return None
        if not _account_is_active_and_current(user_id, tenant_id, payload.get("auth_version")):
            logger.warning("JWT payload references a disabled or stale account")
            return None

        roles = payload.get("roles")
        if not isinstance(roles, list) or not all(isinstance(role, str) for role in roles):
            logger.warning("JWT payload has invalid roles claim")
            return None

        normalized_roles: List[str] = []
        for role in roles:
            normalized = cls.normalize_role_name(role)
            if normalized not in cls.ROLE_PERMISSIONS:
                logger.warning("JWT payload contains unknown role")
                return None
            if normalized not in normalized_roles:
                normalized_roles.append(normalized)

        if not normalized_roles:
            logger.warning("JWT payload contains no valid roles")
            return None

        permissions_claim = payload.get("permissions")
        if permissions_claim is not None and (not isinstance(permissions_claim, list) or not all(isinstance(permission, str) for permission in permissions_claim)):
            logger.warning("JWT payload has invalid permissions claim")
            return None

        trusted_permissions = cls._get_permissions_for_roles(normalized_roles)
        if permissions_claim is not None and any(permission not in trusted_permissions for permission in permissions_claim):
            logger.warning("JWT payload contains permissions not consistent with confirmed roles for user %s", user_id)
            return None

        return User(
            user_id=user_id,
            username=username,
            tenant_id=tenant_id,
            roles=normalized_roles,
            permissions=trusted_permissions,
        )

    @classmethod
    def rotate_refresh_token(
        cls,
        token: str,
        device_id: Optional[str] = None,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> Optional[tuple[User, str]]:
        """Atomically consume a refresh token and issue its replacement.

        Reuse of a consumed or revoked token revokes every token in its family.
        """
        user = cls.verify_refresh_token(token)
        if user is None:
            try:
                payload = jwt.decode(
                    token,
                    _jwt_verification_key(token),
                    algorithms=[ALGORITHM],
                    issuer=JWT_ISSUER,
                    audience=JWT_AUDIENCE,
                    leeway=JWT_LEEWAY_SECONDS,
                    options={"verify_exp": False, "require": _JWT_REQUIRED_CLAIMS},
                )
                family_id = payload.get("family_id")
            except jwt.InvalidTokenError:
                return None
            if isinstance(family_id, str):
                cls._revoke_refresh_family(family_id, "refresh token reuse detected")
            return None

        try:
            payload = jwt.decode(
                token,
                _jwt_verification_key(token),
                algorithms=[ALGORITHM],
                issuer=JWT_ISSUER,
                audience=JWT_AUDIENCE,
                leeway=JWT_LEEWAY_SECONDS,
                options={"require": _JWT_REQUIRED_CLAIMS},
            )
        except jwt.InvalidTokenError:
            return None
        family_id = payload["family_id"]
        jti = payload["jti"]
        _ensure_revocation_store_ready()
        session = _RevocationSession()
        now = datetime.now(timezone.utc)
        try:
            record = session.query(RefreshTokenRecord).filter_by(jti=jti).with_for_update().one_or_none()
            if record is None or record.used_at is not None or record.revoked_at is not None or record.family_revoked:
                session.rollback()
                cls._revoke_refresh_family(family_id, "refresh token reuse detected")
                return None
            if record.device_id and record.device_id != device_id:
                session.rollback()
                cls._revoke_refresh_family(family_id, "refresh token device mismatch")
                return None
            record.used_at = now
            record.revoked_at = now
            session.commit()
        finally:
            session.close()

        replacement = cls.generate_refresh_token(
            user_id=user.user_id,
            username=user.username,
            tenant_id=user.tenant_id,
            roles=user.roles,
            session_id=payload.get("session_id"),
            family_id=family_id,
            device_id=device_id or record.device_id,
            user_agent=user_agent or record.user_agent,
            ip_address=ip_address or record.ip_address,
        )
        return user, replacement

    @classmethod
    def _revoke_refresh_family(cls, family_id: str, reason: str) -> None:
        _ensure_revocation_store_ready()
        session = _RevocationSession()
        try:
            now = datetime.now(timezone.utc)
            session.query(RefreshTokenRecord).filter(
                RefreshTokenRecord.family_id == family_id,
                RefreshTokenRecord.family_revoked.is_(False),
            ).update({
                RefreshTokenRecord.family_revoked: True,
                RefreshTokenRecord.revoked_at: now,
            }, synchronize_session=False)
            session.commit()
            logger.warning("Revoked refresh-token family %s: %s", family_id, reason)
        except Exception:
            session.rollback()
            logger.exception("Failed to revoke refresh-token family %s", family_id)
            raise AuthenticationUnavailable("Refresh-token revocation is unavailable")
        finally:
            session.close()

    @classmethod
    def revoke_session_tokens(cls, session_id: str, reason: str = "session revoked") -> None:
        """Revoke all refresh tokens bound to a server-side session."""
        if not isinstance(session_id, str) or not session_id.strip():
            raise ValueError("session_id must be a non-empty string.")
        _ensure_revocation_store_ready()
        session = _RevocationSession()
        try:
            now = datetime.now(timezone.utc)
            session.query(RefreshTokenRecord).filter(
                RefreshTokenRecord.session_id == session_id,
                RefreshTokenRecord.revoked_at.is_(None),
            ).update({"revoked_at": now}, synchronize_session=False)
            session.commit()
        except Exception as exc:
            session.rollback()
            logger.exception("Failed to revoke refresh tokens for session %s", session_id)
            raise AuthenticationUnavailable("Session revocation is unavailable") from exc
        finally:
            session.close()

    @classmethod
    def _get_permissions_for_roles(cls, roles: List[str]) -> List[str]:
        """Compute the unique set of permission strings for a given list of roles."""
        permissions = set()
        unknown_roles = []
        for role in roles:
            if role in cls.ROLE_PERMISSIONS:
                permissions.update(cls.ROLE_PERMISSIONS[role])
            else:
                unknown_roles.append(role)

        if unknown_roles:
            logger.warning("Unrecognized roles requested during token generation: %s", unknown_roles)
        return sorted(permissions)

    @classmethod
    def is_token_revoked(cls, jti: str) -> bool:
        """Check if a token's JTI exists in the database revocation store."""
        if not isinstance(jti, str) or not jti.strip():
            return True
        _ensure_revocation_store_ready()
        session = _RevocationSession()
        try:
            return session.get(RevokedToken, jti) is not None
        except Exception as exc:
            session.rollback()
            logger.exception("Failed checking token revocation status for JTI %s", jti)
            raise AuthenticationUnavailable("Token revocation status is unavailable") from exc
        finally:
            session.close()

    @classmethod
    def revoke_token(cls, token: str, reason: Optional[str] = None) -> None:
        """Extract a token's JTI and insert it into the distributed revocation table."""
        reason = _sanitize_revocation_reason(reason)
        try:
            payload = jwt.decode(
                token, _jwt_verification_key(token), algorithms=[ALGORITHM],
                options={"verify_exp": False},
            )
        except jwt.InvalidTokenError:
            logger.warning("revoke_token called with unparseable or invalid signature token.")
            return

        jti = payload.get("jti")
        if not jti:
            logger.warning("revoke_token called on token lacking a JTI claim.")
            return

        _ensure_revocation_store_ready()
        session = _RevocationSession()
        try:
            existing = session.get(RevokedToken, jti)
            if not existing:
                session.add(RevokedToken(jti=jti, reason=reason, revoked_at=datetime.now(timezone.utc)))
                session.commit()
                logger.info("Token JTI %s successfully revoked.", jti)
        except Exception as exc:
            logger.exception("Failed to persist token revocation for JTI %s", jti)
            session.rollback()
            raise AuthenticationUnavailable("Token revocation is unavailable") from exc
        finally:
            session.close()

    @classmethod
    def check_permission(cls, user: User, required_permission: str) -> bool:
        """Check if a User principal holds the specified permission string."""
        return required_permission in user.permissions

    @classmethod
    def check_tenant_access(cls, user: User, tenant_id: str) -> bool:
        """Verify that a user is scoped to access the specified tenant_id."""
        return _valid_tenant_id(tenant_id) and (
            user.tenant_id == tenant_id or cls.check_permission(user, "manage:all_tenants")
        )

    @classmethod
    def verify_api_key(cls, api_key: str) -> Optional[User]:
        """Verify a tenant-scoped API key and return a constrained principal."""
        if not isinstance(api_key, str) or not api_key.startswith("pk_"):
            return None

        _ensure_revocation_store_ready()
        try:
            from pesaguard_backend_pipeline.models import ApiKeyRecord
        except ImportError:
            from models import ApiKeyRecord

        key_hash = hashlib.sha256(api_key.encode("utf-8")).hexdigest()
        session = _RevocationSession()
        try:
            record = session.query(ApiKeyRecord).filter(
                ApiKeyRecord.key_hash == key_hash,
                ApiKeyRecord.active.is_(True),
                ApiKeyRecord.revoked_at.is_(None),
            ).first()
            now = datetime.now(timezone.utc)
            if record is None or (record.expires_at is not None and record.expires_at <= now):
                return None

            role = cls.normalize_role_name(record.role)
            if role is None:
                logger.warning("API key %s has an invalid role", record.id)
                return None
            role_permissions = set(cls._get_permissions_for_roles([role]))
            scopes = record.scopes or []
            if not isinstance(scopes, list) or not all(isinstance(scope, str) for scope in scopes):
                return None
            permissions = sorted(role_permissions.intersection(scopes))
            record.last_used_at = now
            session.commit()
            return User(
                user_id=record.id,
                username=f"api-key:{record.key_prefix}",
                tenant_id=record.tenant_id,
                roles=[role],
                permissions=permissions,
            )
        except Exception as exc:
            session.rollback()
            logger.exception("Failed to verify API key")
            raise AuthenticationUnavailable("API-key authentication is unavailable") from exc
        finally:
            session.close()


def require_auth(required_permission: Optional[str] = None):
    """Route decorator enforcing JWT bearer token authentication and permission checks."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            authentication_required = auth_required()
            auth_header = request.headers.get("Authorization", "")
            api_key = request.headers.get("X-API-Key", "").strip()

            if not auth_header and api_key:
                user = AuthRBAC.verify_api_key(api_key)
                if user is None:
                    _record_security_event()
                    return jsonify({"error": "invalid_api_key", "message": "API key is invalid, expired, or revoked."}), 401
            elif not auth_header:
                if not authentication_required:
                    return f(*args, **kwargs)
                _record_security_event()
                return jsonify({"error": "missing_auth_header", "message": "Authorization header is required."}), 401

            else:
                user = getattr(g, "user", None)
                if user is None:
                    token = parse_bearer_token(auth_header)
                    if token is None:
                        _record_security_event()
                        return jsonify({"error": "invalid_auth_header", "message": "Malformed Authorization header format."}), 401
                    try:
                        user = AuthRBAC.verify_token(token)
                    except AuthenticationUnavailable:
                        _record_security_event()
                        return jsonify({
                            "error": "authentication_unavailable",
                            "message": "Authentication state is temporarily unavailable.",
                        }), 503
            if not user:
                _record_security_event()
                return jsonify({"error": "invalid_token", "message": "Token is invalid, expired, or revoked."}), 401

            if required_permission and not AuthRBAC.check_permission(user, required_permission):
                _record_security_event()
                logger.warning("User %s denied access. Required permission: %s", user.user_id, required_permission)
                return jsonify({"error": "insufficient_permissions", "message": "Forbidden: Insufficient privileges."}), 403

            g.user = user
            try:
                from logging_utils import bind_observability_context
                bind_observability_context(tenant_id=user.tenant_id)
            except Exception:
                logger.debug("Unable to bind authenticated observability context", exc_info=True)
            return f(*args, **kwargs)

        return decorated_function

    return decorator


def require_tenant_access():
    """Route decorator enforcing strict tenant boundary isolation matching the caller context."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not hasattr(g, "user") or g.user is None:
                return jsonify({"error": "not_authenticated", "message": "Authentication required."}), 401

            json_payload = request.get_json(silent=True) or {}
            tenant_id = (
                (request.view_args or {}).get("tenant_id")
                or json_payload.get("tenant_id")
                or request.args.get("tenant_id")
            )

            if not tenant_id:
                return jsonify({"error": "missing_tenant_id", "message": "tenant_id parameter is required."}), 400

            if not _valid_tenant_id(tenant_id):
                return jsonify({"error": "invalid_tenant_id", "message": "tenant_id has an invalid format."}), 400

            if not AuthRBAC.check_tenant_access(g.user, tenant_id):
                _record_security_event()
                logger.warning("Tenant access violation attempt by user %s on tenant %s", g.user.user_id, tenant_id)
                return jsonify({"error": "tenant_access_denied", "message": "Access to this tenant scope is forbidden."}), 403

            return f(*args, **kwargs)

        return decorated_function

    return decorator


def get_current_user() -> Optional[User]:
    """Retrieve the authenticated User principal from the Flask request context."""
    return getattr(g, "user", None)
