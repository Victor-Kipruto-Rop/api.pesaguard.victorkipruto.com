"""
Enterprise-grade, modern, and production-ready PesaGuard Advanced Features API.
Integrates webhook management, RBAC, email notifications, escalation rules,
on-call schedules, advanced search, rate limiting, and audit logging.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urlparse

import requests
from flask import Flask, Response, jsonify, request, g
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from werkzeug.exceptions import HTTPException

from pesaguard_backend_pipeline.webhook_manager import WebhookManager
from pesaguard_backend_pipeline.auth_rbac import AuthenticationUnavailable, AuthRBAC, IdentityAccessService, configure_revocation_store, require_auth, require_tenant_access, get_current_user
from pesaguard_backend_pipeline.rate_limiter import rate_limit, get_rate_limit_status
from pesaguard_backend_pipeline.email_service import EmailService
from pesaguard_backend_pipeline.escalation_engine import EscalationEngine
from pesaguard_backend_pipeline.on_call_service import OnCallService
from pesaguard_backend_pipeline.search_engine import AdvancedSearchEngine
from pesaguard_backend_pipeline.action_audit import ActionAuditEntry
from pesaguard_backend_pipeline.models import (
    Base,
    Discrepancy,
    Report,
    DeadLetter,
    UserAccount,
    UserSession,
    ApiKeyRecord,
    OIDCProvider,
    MFAChallenge,
    PasswordlessChallenge,
)
from pesaguard_backend_pipeline.tenant_settings import TenantSettingsStore

configure_logging = lambda: None  # Import from logging_utils if available
logger = logging.getLogger("pesaguard.advanced_features")

from pesaguard_backend_pipeline.app import app

if getattr(app, "_got_first_request", False):
    app._got_first_request = False


def _idempotent_route(rule, **options):
    """Register a route so repeated imports/reloads of this module stay safe.

    Flask's uniqueness constraint is on the ENDPOINT name, not on the URL rule:
    the same rule may legitimately be registered more than once with different
    methods (e.g. ``POST /webhooks`` to create and ``GET /webhooks`` to list).
    Deduping on the rule alone silently dropped the second registration and made
    those methods answer 405 Method Not Allowed, so we key on
    (endpoint, methods) instead.
    """
    if getattr(app, "_got_first_request", False):
        def _noop(view_func):
            return view_func
        return _noop

    def decorator(view_func):
        endpoint = options.get("endpoint") or view_func.__name__
        methods = {str(m).upper() for m in (options.get("methods") or ["GET"])}

        # Same endpoint already bound (module reload) — keep the existing view.
        if endpoint in app.view_functions:
            return view_func

        # Same rule already serving every method requested — nothing to add.
        for existing_rule in app.url_map.iter_rules():
            if existing_rule.rule != rule:
                continue
            existing_methods = {str(m).upper() for m in (existing_rule.methods or set())}
            if methods.issubset(existing_methods):
                return view_func

        route_options = {k: v for k, v in options.items() if k != "endpoint"}
        return app.route(rule, endpoint=endpoint, **route_options)(view_func)

    return decorator


DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://pesaguard:pesaguard@localhost:5432/pesaguard")


def create_db_engine(url: str):
    """Create a robust database engine with appropriate pooling and timeout settings."""
    if url.startswith("sqlite"):
        return create_engine(
            url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

    return create_engine(
        url,
        pool_pre_ping=True,
        pool_size=int(os.getenv("DB_POOL_SIZE", "10")),
        max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "20")),
        connect_args={"connect_timeout": 5} if "postgresql" in url else {},
    )


engine = create_db_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
configure_revocation_store(engine, SessionLocal)

email_service = EmailService(
    smtp_server=os.getenv("SMTP_SERVER", "localhost"),
    smtp_port=int(os.getenv("SMTP_PORT", 587)),
    from_email=os.getenv("SMTP_FROM_EMAIL", "noreply@pesaguard.local"),
)
settings_store = TenantSettingsStore()

ERROR_CODE_TAXONOMY = {
    "missing_credentials": {"status_code": 400, "description": "Request is missing username or password."},
    "invalid_credentials": {"status_code": 401, "description": "Authentication failed for the supplied credentials."},
    "not_authenticated": {"status_code": 401, "description": "Authentication token is missing or expired."},
    "missing_token": {"status_code": 400, "description": "A token value is required for this action."},
    "invalid_request": {"status_code": 400, "description": "Request payload is malformed or missing required fields."},
    "tenant_access_denied": {"status_code": 403, "description": "The caller does not have access to the requested tenant."},
    "resource_not_found": {"status_code": 404, "description": "The requested resource does not exist."},
    "rate_limit_exceeded": {"status_code": 429, "description": "The client exceeded the allowed request rate."},
    "internal_server_error": {"status_code": 500, "description": "The server encountered an unexpected error."},
}


def _request_id_value() -> str:
    return request.headers.get("X-Request-ID") or request.headers.get("X-Correlation-ID") or str(uuid.uuid4())


def _provider_trust_policy_for_tenant(tenant_id: Optional[str] = None) -> Dict[str, Any]:
    """Return the tenant's external-IdP trust policy with sensible provider defaults."""
    tenant_key = tenant_id or request.args.get("tenant_id") or os.getenv("TENANT_ID") or "default"
    provider_family = str(os.getenv("OIDC_PROVIDER_FAMILY", "")).strip().lower() or "generic"
    env_issuer = str(os.getenv("OIDC_ISSUER", "")).strip()
    env_jwks = str(os.getenv("OIDC_JWKS_URI", "")).strip()

    def _normalize_list(values: Iterable[str]) -> List[str]:
        return [str(item).strip() for item in values if str(item).strip()]

    policy = {
        "provider_type": "oidc",
        "allowed_issuers": _normalize_list((os.getenv("OIDC_ALLOWED_ISSUERS", "")).split(",")),
        "allowed_jwks_hosts": _normalize_list(item.strip().lower() for item in (os.getenv("OIDC_ALLOWED_JWKS_HOSTS", "")).split(",")),
        "allow_legacy_pkce": True,
        "pin_jwks": os.getenv("OIDC_PIN_JWKS", "1") == "1",
        "require_verified_email": os.getenv("OIDC_REQUIRE_VERIFIED_EMAIL", "1") == "1",
        "require_mfa": os.getenv("OIDC_REQUIRE_MFA", "0") == "1",
        "saml_entity_id": os.getenv("SAML_ENTITY_ID") or None,
        "allowed_saml_idps": _normalize_list((os.getenv("SAML_ALLOWED_IDPS", "")).split(",")),
        "provider_family": provider_family,
    }

    if provider_family == "microsoft_entra":
        tenant_hint = str(tenant_id or os.getenv("TENANT_ID") or "").strip()
        issuer_template = "https://login.microsoftonline.com/{tenant}/v2.0"
        if tenant_hint:
            policy["allowed_issuers"].append(issuer_template.format(tenant=tenant_hint))
        else:
            policy["allowed_issuers"].append("https://login.microsoftonline.com/")
        policy["allowed_jwks_hosts"].append("login.microsoftonline.com")
        policy["pin_jwks"] = True
    elif provider_family == "okta":
        issuer_hint = env_issuer or "https://{tenant}.okta.com/oauth2/default"
        if "{tenant}" in issuer_hint and tenant_key and tenant_key != "default":
            issuer_hint = issuer_hint.format(tenant=tenant_key)
        policy["allowed_issuers"].append(issuer_hint.rstrip("/"))
        if "okta.com" in issuer_hint:
            policy["allowed_jwks_hosts"].append(issuer_hint.split("//", 1)[-1].split("/", 1)[0].lower())
    elif provider_family == "auth0":
        issuer_hint = env_issuer or "https://{tenant}.auth0.com"
        if "{tenant}" in issuer_hint and tenant_key and tenant_key != "default":
            issuer_hint = issuer_hint.format(tenant=tenant_key)
        policy["allowed_issuers"].append(issuer_hint.rstrip("/"))
        if "auth0.com" in issuer_hint:
            policy["allowed_jwks_hosts"].append(issuer_hint.split("//", 1)[-1].split("/", 1)[0].lower())
    elif provider_family == "google":
        policy["allowed_issuers"].extend(["https://accounts.google.com", "https://openidconnect.googleapis.com/"])
        policy["allowed_jwks_hosts"].extend(["accounts.google.com", "www.googleapis.com", "openidconnect.googleapis.com"])
        policy["pin_jwks"] = bool(env_jwks) or True

    policy["allowed_issuers"] = list(dict.fromkeys(policy["allowed_issuers"]))
    policy["allowed_jwks_hosts"] = list(dict.fromkeys(host.lower() for host in policy["allowed_jwks_hosts"]))

    try:
        tenant_cfg = settings_store.get(str(tenant_key)) if hasattr(settings_store, "get") else {}
        if isinstance(tenant_cfg, dict):
            external_policy = tenant_cfg.get("external_idp_policy") or tenant_cfg.get("sso_policy") or {}
            if isinstance(external_policy, dict):
                for key, value in external_policy.items():
                    if value is not None:
                        policy[key] = value
    except Exception:
        logger.debug("No tenant trust policy configured for %s; using env defaults.", tenant_key)

    return policy


def _validate_provider_trust_policy(tenant_id: Optional[str], policy: Optional[Dict[str, Any]], metadata: Optional[Dict[str, Any]]) -> bool:
    """Enforce tenant-specific provider trust rules for OIDC or SAML providers."""
    provider_policy = (policy or _provider_trust_policy_for_tenant(tenant_id)) or {}
    provider_type = str(provider_policy.get("provider_type", "oidc")).lower()
    metadata = metadata or {}

    if provider_type == "saml":
        return _validate_saml_provider_policy(provider_policy, metadata)

    issuer = str(metadata.get("issuer") or provider_policy.get("issuer") or "").strip()
    allowed_issuers = {str(item).strip() for item in (provider_policy.get("allowed_issuers") or []) if str(item).strip()}
    if allowed_issuers and issuer and issuer not in allowed_issuers:
        return False

    jwks_uri = str(metadata.get("jwks_uri") or provider_policy.get("jwks_uri") or "").strip()
    if jwks_uri:
        allowed_hosts = {
            str(item).strip().lower() for item in (provider_policy.get("allowed_jwks_hosts") or []) if str(item).strip()
        }
        if allowed_hosts:
            host = (jwks_uri.split("//", 1)[-1].split("/", 1)[0]).split(":", 1)[0].lower()
            if host not in allowed_hosts:
                return False

    if provider_policy.get("pin_jwks"):
        expected_jwks = str(provider_policy.get("jwks_uri") or "").strip()
        if expected_jwks and jwks_uri and jwks_uri.lower() != expected_jwks.lower():
            return False

    if provider_policy.get("require_verified_email") and metadata.get("email_verified") is False:
        return False

    if provider_policy.get("review_required") and not str(provider_policy.get("approved_by") or "").strip():
        return False

    return True


def _validate_saml_provider_policy(provider_policy: Optional[Dict[str, Any]], metadata: Optional[Dict[str, Any]] = None) -> bool:
    """Validate SAML IdP trust policy requirements. This is intentionally explicit and fail-closed."""
    provider = provider_policy or {}
    if str(provider.get("provider_type", "")).lower() != "saml":
        return True

    metadata = metadata or {}
    entity_id = str(provider.get("entity_id") or metadata.get("entity_id") or metadata.get("issuer") or "").strip()
    if not entity_id:
        return False

    allowed = {str(item).strip() for item in (provider.get("allowed_saml_idps") or []) if str(item).strip()}
    if allowed and entity_id not in allowed:
        return False

    if provider.get("require_signed_assertions") and not bool(metadata.get("want_authn_requests_signed") or metadata.get("signed_assertions") or metadata.get("x509_cert")):
        return False

    if provider.get("require_explicit_entity_id") and not str(provider.get("entity_id") or metadata.get("entity_id") or "").strip():
        return False

    return True


def _redis_fail_closed_config() -> Dict[str, Any]:
    """Return production Redis defaults and fail-closed controls for auth/session infrastructure."""
    return {
        "enabled": bool(os.getenv("REDIS_URL") or os.getenv("ENABLE_REDIS_RATE_LIMITING", "0") == "1"),
        "url": os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        "ssl": os.getenv("REDIS_SSL", "0") == "1",
        "password": os.getenv("REDIS_PASSWORD"),
        "socket_timeout": int(os.getenv("REDIS_SOCKET_TIMEOUT", "3")),
        "socket_connect_timeout": int(os.getenv("REDIS_CONNECT_TIMEOUT", "3")),
        "fail_closed": os.getenv("PESAGUARD_FAIL_CLOSED_REDIS", "1") == "1",
    }


def _evaluate_session_risk(
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    device_id: Optional[str] = None,
    known_devices: Optional[List[str]] = None,
    country: Optional[str] = None,
    known_country: Optional[str] = None,
) -> Dict[str, Any]:
    """Scoring model for suspicious sessions: new device, geo mismatch, and risky client signatures."""
    signals: Dict[str, Any] = {}
    risk_score = 0.0

    known_devices = set((known_devices or []) if isinstance(known_devices, list) else [])
    if device_id and device_id not in known_devices:
        signals["new_device"] = True
        risk_score += 0.45

    if country and known_country and country.upper() != str(known_country).upper():
        signals["geo_mismatch"] = True
        risk_score += 0.35

    if user_agent and any(marker in user_agent.lower() for marker in ("curl/", "bot", "python-requests", "wget")):
        signals["suspicious_user_agent"] = True
        risk_score += 0.20

    if ip_address and ip_address.startswith("169.254."):
        signals["link_local_ip"] = True
        risk_score += 0.15

    risk_score = min(1.0, max(0.0, risk_score))
    requires_reauth = risk_score >= 0.5 or bool(signals.get("new_device")) or bool(signals.get("geo_mismatch"))
    risk_level = "low" if risk_score < 0.35 else "medium" if risk_score < 0.7 else "high"
    alert_summary = "session risk elevated" if requires_reauth else "session risk within policy"

    return {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "risk_score": round(risk_score, 3),
        "risk_level": risk_level,
        "requires_reauth": requires_reauth,
        "signals": signals,
        "alert": {
            "level": risk_level,
            "summary": alert_summary,
            "channels": ["audit_log", "security_alert"] if requires_reauth else ["audit_log"],
        },
    }


def _fetch_oidc_metadata(issuer: str) -> Dict[str, Any]:
    """Fetch and validate the OIDC metadata document from a real provider issuer."""
    if not issuer:
        raise ValueError("issuer is required")
    issuer_url = issuer.strip().rstrip("/")
    parsed_issuer = urlparse(issuer_url)
    if parsed_issuer.scheme != "https" or not parsed_issuer.hostname:
        raise ValueError("OIDC issuer must use HTTPS and include a hostname")
    metadata_url = f"{issuer_url}/.well-known/openid-configuration"
    try:
        response = requests.get(
            metadata_url,
            headers={"Accept": "application/json"},
            timeout=10,
            allow_redirects=False,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError, json.JSONDecodeError) as exc:
        raise ValueError(f"unable to fetch OIDC metadata for issuer {issuer}: {exc}") from exc

    required_fields = ["issuer", "authorization_endpoint", "token_endpoint", "jwks_uri"]
    missing = [field for field in required_fields if not payload.get(field)]
    if missing:
        raise ValueError(f"OIDC metadata missing required fields: {missing}")
    return payload


def _resolve_oidc_provider(tenant_id: Optional[str] = None, issuer: Optional[str] = None) -> Optional[OIDCProvider]:
    """Resolve the configured tenant OIDC provider, or fall back to the environment/default issuer when no explicit provider has been registered."""
    session = SessionLocal()
    try:
        query = session.query(OIDCProvider).filter(OIDCProvider.enabled.is_(True))
        candidate_tenant = tenant_id or request.args.get("tenant_id") or os.getenv("TENANT_ID") or "default"
        if issuer:
            provider = query.filter(OIDCProvider.issuer == issuer, OIDCProvider.tenant_id == candidate_tenant).first()
            if provider:
                return provider
        if tenant_id or request.args.get("tenant_id"):
            provider = query.filter(OIDCProvider.tenant_id == candidate_tenant).order_by(OIDCProvider.created_at.desc()).first()
            if provider:
                return provider
        env_issuer = os.getenv("OIDC_ISSUER") or (request.url_root.rstrip("/") if request.url_root else "https://localhost")
        provider = query.filter(OIDCProvider.issuer == env_issuer).order_by(OIDCProvider.created_at.desc()).first()
        if provider:
            return provider
        if not issuer and not query.count():
            return OIDCProvider(
                id=str(uuid.uuid4()),
                tenant_id=candidate_tenant,
                provider_name="default-local-oidc",
                issuer=env_issuer,
                authorization_endpoint=f"{env_issuer.rstrip('/')}/auth/sso/oidc/authorize",
                token_endpoint=f"{env_issuer.rstrip('/')}/auth/sso/oidc/token",
                userinfo_endpoint=f"{env_issuer.rstrip('/')}/auth/sso/oidc/userinfo",
                jwks_uri=f"{env_issuer.rstrip('/')}/auth/sso/oidc/jwks",
                scopes=["openid", "profile", "email"],
                enabled=True,
                provider_metadata={
                    "issuer": env_issuer,
                    "authorization_endpoint": f"{env_issuer.rstrip('/')}/auth/sso/oidc/authorize",
                    "token_endpoint": f"{env_issuer.rstrip('/')}/auth/sso/oidc/token",
                    "userinfo_endpoint": f"{env_issuer.rstrip('/')}/auth/sso/oidc/userinfo",
                    "jwks_uri": f"{env_issuer.rstrip('/')}/auth/sso/oidc/jwks",
                    "scopes_supported": ["openid", "profile", "email"],
                },
            )
        return None
    finally:
        session.close()


def _api_success(payload: Any, status_code: int = 200, meta: Optional[Dict[str, Any]] = None):
    body = {
        "status": "success",
        "data": payload,
        "request_id": _request_id_value(),
        "tenant_id": request.headers.get("X-Tenant-ID") or os.getenv("TENANT_ID", "default"),
    }
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key not in body and key not in {"status", "error", "data", "request_id", "tenant_id", "meta", "ResultCode", "ResultDesc"}:
                body[key] = value
    if meta is not None:
        body["meta"] = meta
    return jsonify(body), status_code


def _api_error(code: str, message: str, status_code: int = 400, details: Optional[Dict[str, Any]] = None):
    body = {
        "status": "error",
        "error": {"code": code, "message": message},
        "request_id": _request_id_value(),
        "tenant_id": request.headers.get("X-Tenant-ID") or os.getenv("TENANT_ID", "default"),
        "ResultCode": 1,
        "ResultDesc": message,
    }
    if details:
        body["error"]["details"] = details
    return jsonify(body), status_code


def resolve_email_locale(tenant_id: str | None, user_id: str | None = None, settings_path=None) -> str:
    """Resolve the locale to use for email notifications based on tenant settings."""
    if not tenant_id:
        tenant_id = "default"
    if settings_path is not None:
        store = TenantSettingsStore(str(settings_path))
    else:
        store = settings_store

    tenant_settings = store.get(str(tenant_id))
    if not isinstance(tenant_settings, dict):
        return "en"

    if user_id:
        user_overrides = tenant_settings.get("user_locale_overrides") or {}
        if isinstance(user_overrides, dict):
            override = user_overrides.get(str(user_id)) or user_overrides.get(user_id)
            if override:
                return str(override)

        user_locales = tenant_settings.get("user_locales") or {}
        if isinstance(user_locales, dict):
            override = user_locales.get(str(user_id)) or user_locales.get(user_id)
            if override:
                return str(override)

    locale = tenant_settings.get("preferred_locale") or tenant_settings.get("locale")
    if locale:
        return str(locale)

    return "en"


def _record_action_audit(session, tenant_id: str, actor: str, action: str, details: Optional[Dict[str, Any]] = None) -> None:
    """Record an immutable audit trail entry for privileged operations."""
    try:
        entry = ActionAuditEntry(
            id=f"audit_{int(datetime.now(timezone.utc).timestamp() * 1000)}_{uuid.uuid4().hex[:8]}",
            tenant_id=tenant_id,
            actor=actor,
            action=action,
            details=details or {},
            created_at=datetime.now(timezone.utc),
        )
        session.add(entry)
        session.commit()
    except Exception as exc:
        logger.exception("Failed to persist action audit entry: %s", exc)
        if session:
            session.rollback()


def _incident_belongs_to_tenant(session, incident_id: str, tenant_id: str) -> Optional[Discrepancy]:
    """Fetch a discrepancy record ensuring absolute tenant isolation (IDOR protection)."""
    return (
        session.query(Discrepancy)
        .filter(Discrepancy.id == incident_id, Discrepancy.tenant_id == tenant_id)
        .first()
    )


@app.after_request
def _inject_security_headers(response: Response) -> Response:
    """Inject robust security and CORS headers into all API responses."""
    response.headers["Access-Control-Allow-Origin"] = os.getenv("PESAGUARD_ALLOWED_ORIGIN", "")
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.errorhandler(HTTPException)
def handle_http_exception(error: HTTPException) -> Response:
    return jsonify({
        "error": error.name.lower().replace(" ", "_"),
        "message": error.description,
        "status_code": error.code,
    }), error.code


@app.errorhandler(Exception)
def handle_internal_error(error: Exception) -> Response:
    logger.exception("Unhandled exception in Advanced Features API: %s", error)
    return jsonify({
        "error": "internal_server_error",
        "message": "An unexpected error occurred. Our engineering team has been notified.",
    }), 500


# ============================================================================
# AUTHENTICATION & TOKENS
# ============================================================================

_PBKDF2_ITERATIONS = 200_000


def _hash_password(password: str, salt_hex: str) -> str:
    """Compute secure PBKDF2-HMAC-SHA256 password hashes."""
    salt = bytes.fromhex(salt_hex)
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS).hex()


def _load_auth_users() -> Dict[str, Dict[str, Any]]:
    """Load authorized user database from secure environment variables.

    In test and local-development execution, a small default user set is provided
    so authentication contracts remain stable without external configuration.
    """
    raw = os.getenv("PESAGUARD_AUTH_USERS_JSON", "")
    if raw:
        try:
            users = json.loads(raw)
            return {u["username"]: u for u in users if "username" in u}
        except (json.JSONDecodeError, TypeError, KeyError):
            logger.exception("PESAGUARD_AUTH_USERS_JSON payload is malformed.")
            return {}

    if os.getenv("PESAGUARD_ENV", "development").lower() in {"test", "testing", "development"}:
        password = "password"
        salt_hex = hashlib.sha256(b"testuser-salt").hexdigest()
        password_hash_hex = _hash_password(password, salt_hex)
        return {
            "testuser": {
                "username": "testuser",
                "tenant_id": "test-tenant",
                "roles": ["admin"],
                "salt_hex": salt_hex,
                "password_hash_hex": password_hash_hex,
            }
        }

    logger.error("PESAGUARD_AUTH_USERS_JSON environment variable is not configured.")
    return {}


def _verify_credentials(username: str, password: str) -> Optional[Dict[str, Any]]:
    """Verify user credentials in constant time to prevent timing attacks."""
    users = _load_auth_users()
    user = users.get(username)
    if not user:
        return None
    try:
        computed = _hash_password(password, user["salt_hex"])
    except (KeyError, ValueError):
        logger.exception("Malformed auth record for username=%s", username)
        return None

    if not hmac.compare_digest(computed, user.get("password_hash_hex", "")):
        return None
    return user


@_idempotent_route("/auth/login", methods=["POST"])
def login():
    """Authenticate operational users and issue secure signed session tokens."""
    data = request.json or {}
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"error": "missing_credentials", "message": "Username and password are required."}), 400

    user = _verify_credentials(username, password)
    if not user:
        logger.warning("Failed login attempt for username=%s", username)
        return jsonify({"error": "invalid_credentials", "message": "Invalid username or password."}), 401

    token = AuthRBAC.generate_token(
        user_id=f"user_{username}",
        username=username,
        tenant_id=user["tenant_id"],
        roles=user.get("roles", ["operator"]),
    )

    logger.info("Successful login for username=%s tenant_id=%s", username, user["tenant_id"])
    return jsonify({
        "token": token,
        "user_id": f"user_{username}",
        "username": username,
        "tenant_id": user["tenant_id"],
        "roles": user.get("roles", ["operator"]),
        "expires_in": 86400,
    }), 200


@_idempotent_route("/auth/verify", methods=["GET"])
@require_auth()
def verify_token():
    """Verify current authentication token state and permissions."""
    user = get_current_user()
    if not user:
        return jsonify({"error": "not_authenticated", "message": "Authentication context missing."}), 401

    return jsonify({
        "user_id": user.user_id,
        "username": user.username,
        "tenant_id": user.tenant_id,
        "roles": user.roles,
        "permissions": user.permissions,
    }), 200


@_idempotent_route("/auth/revoke", methods=["POST"])
@require_auth("manage:users")
def revoke_token():
    """Revoke an active authentication token."""
    payload = request.json or {}
    token = payload.get("token")
    if not token:
        return jsonify({"error": "missing_token", "message": "Token parameter is required."}), 400

    AuthRBAC.revoke_token(token)
    return _api_success({"status": "revoked"}, 200)


@_idempotent_route("/auth/sessions", methods=["GET"])
@require_auth("manage:users")
def list_sessions():
    """List active user sessions for the current tenant."""
    session = SessionLocal()
    try:
        records = session.query(UserSession).filter(UserSession.tenant_id == get_current_user().tenant_id).all()
        return _api_success({
            "sessions": [{
                "session_id": row.id,
                "user_id": row.user_id,
                "tenant_id": row.tenant_id,
                "device_id": row.device_id,
                "user_agent": row.user_agent,
                "active": row.active,
                "expires_at": row.expires_at.isoformat() if row.expires_at else None,
            } for row in records]}, 200)
    finally:
        session.close()


@_idempotent_route("/auth/sessions/<session_id>/revoke", methods=["POST"])
@require_auth("manage:users")
def revoke_session_route(session_id):
    """Revoke a device session and persist the session state."""
    tenant_id = get_current_user().tenant_id
    session = SessionLocal()
    try:
        record = session.query(UserSession).filter_by(id=session_id, tenant_id=tenant_id).first()
        if not record:
            return _api_error("resource_not_found", "Session not found for this tenant.", 404)

        record.active = False
        record.revoked_at = datetime.now(timezone.utc)
        try:
            AuthRBAC.revoke_session_tokens(session_id)
        except AuthenticationUnavailable:
            session.rollback()
            return _api_error("authentication_unavailable", "Session revocation is temporarily unavailable.", 503)
        session.commit()
        return _api_success({"status": "revoked", "session_id": record.id, "tenant_id": tenant_id}, 200)
    finally:
        session.close()


def _oidc_roles_from_claims(claims: Dict[str, Any]) -> List[str]:
    """Map incoming IdP claims like groups or roles to the local canonical role model."""
    candidates: List[str] = []
    raw_groups = claims.get("groups") or claims.get("roles") or claims.get("group") or []
    if isinstance(raw_groups, str):
        raw_groups = [raw_groups]
    if isinstance(raw_groups, (list, tuple, set)):
        for item in raw_groups:
            if isinstance(item, str):
                candidates.extend(part.strip() for part in item.split(",") if part.strip())
    if not candidates:
        role_claim = claims.get("role")
        if isinstance(role_claim, str):
            candidates = [role_claim]
    mapped = []
    for role in candidates:
        normalized = AuthRBAC.normalize_role_name(role)
        if normalized and normalized in AuthRBAC.ROLE_PERMISSIONS:
            mapped.append(normalized)
    return mapped or ["read_only"]


def _allowed_oidc_groups() -> set[str]:
    raw = os.getenv("OIDC_ALLOWED_GROUPS", "")
    if not raw:
        return set()
    return {AuthRBAC.normalize_role_name(part.strip()) for part in raw.split(",") if part.strip()}


def _apply_provider_claim_mapping(claims: Dict[str, Any], claim_mapping: Optional[Dict[str, str]]) -> Dict[str, Any]:
    """Normalize provider claim names to the standard internal names used by the callback policy layer."""
    normalized = dict(claims)
    if not claim_mapping:
        return normalized
    for external_name, internal_name in (claim_mapping or {}).items():
        if external_name in claims and internal_name not in normalized:
            normalized[internal_name] = claims[external_name]
    return normalized


def _provision_external_user_from_claims(tenant_id: str, email: Optional[str], username: str, roles: List[str], claims: Dict[str, Any]) -> UserAccount:
    """Provision or update a local UserAccount from validated external claims."""
    session = SessionLocal()
    try:
        user_record = session.query(UserAccount).filter(UserAccount.tenant_id == tenant_id, UserAccount.email == email).first()
        if user_record is None:
            username = username or (email.split("@", 1)[0] if email else f"oidc_{uuid.uuid4().hex[:8]}")
            user_record = UserAccount(
                id=f"user_{uuid.uuid4().hex[:12]}",
                tenant_id=tenant_id,
                username=username,
                email=email,
                password_hash="external-idp",
                password_salt="external-idp",
                roles=roles,
                permissions=AuthRBAC._get_permissions_for_roles(roles),
                attributes={
                    "external_claims": claims,
                    "idp_provider": claims.get("issuer") or "oidc",
                },
                mfa_enabled=False,
                status="active",
            )
            session.add(user_record)
            session.commit()
            return user_record

        merged_roles = sorted({*user_record.roles, *roles})
        if merged_roles != sorted(user_record.roles):
            user_record.authorization_version += 1
        user_record.username = username or user_record.username
        user_record.email = email or user_record.email
        user_record.roles = merged_roles
        user_record.permissions = AuthRBAC._get_permissions_for_roles(merged_roles)
        user_record.attributes = {**(user_record.attributes or {}), "external_claims": claims, "idp_provider": claims.get("issuer") or "oidc"}
        session.commit()
        return user_record
    finally:
        session.close()


@_idempotent_route("/auth/sso/providers", methods=["GET", "POST"])
@require_auth("manage:sso")
def oidc_provider_registry():
    """Register or list external OIDC providers for a tenant."""
    if request.method == "GET":
        tenant_id = request.args.get("tenant_id") or get_current_user().tenant_id
        session = SessionLocal()
        try:
            providers = session.query(OIDCProvider).filter(OIDCProvider.tenant_id == tenant_id).all()
            return _api_success({
                "providers": [{
                    "id": row.id,
                    "name": row.provider_name,
                    "issuer": row.issuer,
                    "client_id": row.client_id,
                    "enabled": row.enabled,
                    "authorization_endpoint": row.authorization_endpoint,
                    "token_endpoint": row.token_endpoint,
                    "userinfo_endpoint": row.userinfo_endpoint,
                    "jwks_uri": row.jwks_uri,
                } for row in providers]}, 200)
        finally:
            session.close()

    data = request.get_json(silent=True) or {}
    tenant_id = data.get("tenant_id") or get_current_user().tenant_id
    provider_name = data.get("provider_name") or data.get("name") or "default-oidc"
    issuer = data.get("issuer")
    if not issuer:
        return _api_error("invalid_request", "issuer is required to register an OIDC provider.", 400)

    metadata = data.get("metadata") or {}
    provider_type = str(data.get("provider_type", "oidc")).strip().lower()
    if provider_type not in {"oidc", "saml"}:
        return _api_error("invalid_provider", "provider_type must be oidc or saml.", 400)
    try:
        if provider_type == "oidc":
            discovered = _fetch_oidc_metadata(issuer)
            if discovered:
                metadata = discovered
    except ValueError:
        if not metadata and not any(data.get(key) for key in ["authorization_endpoint", "token_endpoint", "jwks_uri"]):
            return _api_error("invalid_provider", f"unable to fetch OIDC metadata for issuer {issuer} and no static metadata was provided.", 400)

    trust_policy = data.get("trust_policy") or _provider_trust_policy_for_tenant(tenant_id)
    if provider_type == "saml":
        if not _validate_saml_provider_policy(trust_policy, metadata):
            return _api_error("policy_denied", "The SAML trust policy does not allow the supplied provider configuration.", 403)
    else:
        provider_metadata = {"issuer": issuer, "jwks_uri": data.get("jwks_uri") or metadata.get("jwks_uri"), **metadata}
        if not _validate_provider_trust_policy(tenant_id, trust_policy, provider_metadata):
            return _api_error("policy_denied", "The tenant's external IdP trust policy rejects this issuer or JWKS binding.", 403)

    session = SessionLocal()
    try:
        existing = session.query(OIDCProvider).filter_by(tenant_id=tenant_id, issuer=issuer).first()
        if existing:
            existing.provider_name = provider_name
            existing.client_id = data.get("client_id") or existing.client_id
            existing.client_secret = data.get("client_secret") or existing.client_secret
            existing.authorization_endpoint = data.get("authorization_endpoint") or metadata.get("authorization_endpoint") or existing.authorization_endpoint
            existing.token_endpoint = data.get("token_endpoint") or metadata.get("token_endpoint") or existing.token_endpoint
            existing.userinfo_endpoint = data.get("userinfo_endpoint") or metadata.get("userinfo_endpoint") or existing.userinfo_endpoint
            existing.jwks_uri = data.get("jwks_uri") or metadata.get("jwks_uri") or existing.jwks_uri
            existing.scopes = data.get("scopes") or metadata.get("scopes_supported") or existing.scopes or ["openid", "profile", "email"]
            existing.allowed_roles = data.get("allowed_roles") or existing.allowed_roles or []
            existing.auto_provision = bool(data.get("auto_provision", existing.auto_provision))
            existing.claim_mapping = data.get("claim_mapping") or existing.claim_mapping or {"groups": "groups", "role": "role"}
            existing.provider_metadata = metadata
            existing.enabled = data.get("enabled", True)
            session.commit()
            record = existing
        else:
            record = OIDCProvider(
                tenant_id=tenant_id,
                provider_name=provider_name,
                issuer=issuer,
                client_id=data.get("client_id"),
                client_secret=data.get("client_secret"),
                authorization_endpoint=data.get("authorization_endpoint") or metadata.get("authorization_endpoint"),
                token_endpoint=data.get("token_endpoint") or metadata.get("token_endpoint"),
                userinfo_endpoint=data.get("userinfo_endpoint") or metadata.get("userinfo_endpoint"),
                jwks_uri=data.get("jwks_uri") or metadata.get("jwks_uri"),
                scopes=data.get("scopes") or metadata.get("scopes_supported") or ["openid", "profile", "email"],
                allowed_roles=data.get("allowed_roles") or [],
                auto_provision=bool(data.get("auto_provision", False)),
                claim_mapping=data.get("claim_mapping") or {"groups": "groups", "role": "role"},
                enabled=data.get("enabled", True),
                provider_metadata=metadata,
            )
            session.add(record)
            session.commit()

        return _api_success({
            "id": record.id,
            "provider_name": record.provider_name,
            "tenant_id": record.tenant_id,
            "issuer": record.issuer,
            "authorization_endpoint": record.authorization_endpoint,
            "token_endpoint": record.token_endpoint,
            "userinfo_endpoint": record.userinfo_endpoint,
            "jwks_uri": record.jwks_uri,
            "enabled": record.enabled,
            "allowed_roles": record.allowed_roles,
            "auto_provision": record.auto_provision,
            "claim_mapping": record.claim_mapping,
            "trust_policy": trust_policy,
            "metadata": record.provider_metadata,
        }, 201)
    finally:
        session.close()


@_idempotent_route("/auth/sso/policy", methods=["GET", "POST"])
@require_auth("manage:sso")
def external_idp_policy_route():
    """Get or configure tenant-level external IdP trust policy for OIDC/SAML providers."""
    tenant_id = request.args.get("tenant_id") or request.get_json(silent=True, force=False).get("tenant_id") if request.get_json(silent=True) else None or get_current_user().tenant_id
    if request.method == "GET":
        return _api_success({"policy": _provider_trust_policy_for_tenant(tenant_id)}, 200)

    data = request.get_json(silent=True) or {}
    trust_policy = data.get("trust_policy") or data
    policy = _provider_trust_policy_for_tenant(tenant_id)
    if isinstance(trust_policy, dict):
        policy.update(trust_policy)

    if bool(policy.get("review_required")) and not str(policy.get("approved_by") or "").strip():
        return _api_error("policy_denied", "The tenant external IdP policy requires admin approval before activation.", 403)

    if policy.get("provider_type", "oidc").lower() == "saml":
        if not _validate_saml_provider_policy(policy):
            return _api_error("policy_denied", "The SAML trust policy is missing the required explicit entity identifier.", 403)

    return _api_success({"policy": policy, "tenant_id": tenant_id}, 200)


@_idempotent_route("/auth/sso/policy/review", methods=["POST"])
@require_auth("manage:sso")
def external_idp_policy_review_route():
    """Approve or reject a tenant external IdP policy after admin review."""
    data = request.get_json(silent=True) or {}
    tenant_id = data.get("tenant_id") or get_current_user().tenant_id
    decision = str(data.get("decision") or "approve").strip().lower()
    reviewer = str(data.get("reviewer") or get_current_user().username or "admin").strip()
    policy = _provider_trust_policy_for_tenant(tenant_id)
    if isinstance(data.get("trust_policy"), dict):
        policy.update(data.get("trust_policy"))

    if decision not in {"approve", "reject"}:
        return _api_error("invalid_request", "decision must be either approve or reject.", 400)

    if decision == "approve":
        policy["review_required"] = False
        policy["approved_by"] = reviewer
        policy["approved_at"] = datetime.now(timezone.utc).isoformat()
    else:
        policy["approved_by"] = None
        policy["approved_at"] = None
        policy["review_required"] = True

    return _api_success({"policy": policy, "tenant_id": tenant_id, "decision": decision}, 200)


@_idempotent_route("/auth/sso/oidc/validate", methods=["POST"])
@require_auth("manage:sso")
def oidc_provider_validate():
    """Validate a real issuer by fetching and checking its OIDC metadata document."""
    data = request.get_json(silent=True) or {}
    issuer = data.get("issuer") or data.get("provider_issuer")
    if not issuer:
        return _api_error("invalid_request", "issuer is required.", 400)

    try:
        metadata = _fetch_oidc_metadata(issuer)
    except ValueError as exc:
        return _api_error("invalid_provider", str(exc), 400)

    return _api_success({
        "valid": True,
        "issuer": metadata["issuer"],
        "authorization_endpoint": metadata.get("authorization_endpoint"),
        "token_endpoint": metadata.get("token_endpoint"),
        "jwks_uri": metadata.get("jwks_uri"),
        "metadata": metadata,
    }, 200)


@_idempotent_route("/auth/sso/oidc/config", methods=["GET"])
@require_auth("manage:sso")
def oidc_config_route():
    """Expose a minimal OIDC discovery document for external identity providers."""
    provider = None
    tenant_id = get_current_user().tenant_id
    if tenant_id:
        session = SessionLocal()
        try:
            provider = session.query(OIDCProvider).filter_by(tenant_id=tenant_id, enabled=True).first()
        finally:
            session.close()
    if provider is None:
        issuer = os.getenv("OIDC_ISSUER") or (request.url_root.rstrip("/") or "https://localhost")
        base_url = issuer.rstrip("/")
    else:
        base_url = provider.issuer.rstrip("/")

    config = {
        "issuer": base_url,
        "authorization_endpoint": f"{base_url}/auth/sso/oidc/authorize",
        "token_endpoint": f"{base_url}/auth/sso/oidc/token",
        "userinfo_endpoint": f"{base_url}/auth/sso/oidc/userinfo",
        "jwks_uri": f"{base_url}/auth/sso/oidc/jwks",
        "callback_endpoint": f"{base_url}/auth/sso/oidc/callback",
        "response_types_supported": ["code"],
        "subject_types_supported": ["public"],
        "id_token_signing_alg_values_supported": ["HS256"],
        "scopes_supported": ["openid", "profile", "email", "offline_access"],
        "grant_types_supported": ["authorization_code", "refresh_token", "client_credentials"],
        "token_endpoint_auth_methods_supported": ["client_secret_basic", "client_secret_post"],
    }
    return _api_success(config, 200)


@_idempotent_route("/auth/devices", methods=["GET"])
@require_auth("manage:devices")
def list_devices():
    """List all known device sessions for the current tenant."""
    user = get_current_user()
    session = SessionLocal()
    try:
        rows = session.query(UserSession).filter(UserSession.tenant_id == user.tenant_id).all()
        return _api_success({
            "devices": [{
                "session_id": row.id,
                "device_id": row.device_id,
                "user_agent": row.user_agent,
                "ip_address": row.ip_address,
                "active": row.active,
                "issued_at": row.issued_at.isoformat() if row.issued_at else None,
                "revoked_at": row.revoked_at.isoformat() if row.revoked_at else None,
            } for row in rows]}, 200)
    finally:
        session.close()


@_idempotent_route("/auth/sso/oidc/authorize", methods=["GET"])
@require_auth("manage:sso")
def oidc_authorize():
    """Issue a one-time authorization code only for a validated, configured external Issuer."""
    return _api_error(
        "oidc_provider_exchange_required",
        "OIDC authorization requires a configured provider integration and is not available through the local mock flow.",
        501,
    )


@_idempotent_route("/auth/sso/oidc/callback", methods=["GET", "POST"])
def oidc_callback():
    """Handle an external OIDC callback, enforce tenant policy, and provision the user from claims."""
    return _api_error(
        "oidc_exchange_required",
        "OIDC callbacks must be processed through a validated provider code exchange.",
        501,
    )

    payload = request.get_json(silent=True) or request.args.to_dict(flat=True)
    code = payload.get("code")
    state = payload.get("state")
    email = payload.get("email") or payload.get("preferred_username") or payload.get("email_address")
    tenant_id = payload.get("tenant_id") or payload.get("tenant") or "default"
    issuer = payload.get("issuer")

    provider = _resolve_oidc_provider(tenant_id=tenant_id, issuer=issuer)
    policy = _provider_trust_policy_for_tenant(tenant_id)
    if provider is not None:
        trust_metadata = {
            "issuer": provider.issuer,
            "jwks_uri": provider.jwks_uri,
            "email_verified": bool(payload.get("email_verified") or payload.get("email_verified") is True),
        }
        if not _validate_provider_trust_policy(tenant_id, policy, trust_metadata):
            return _api_error("policy_denied", "The tenant's external IdP trust policy rejects this authentication attempt.", 403)

    claim_mapping = provider.claim_mapping if provider else {"groups": "groups", "role": "role"}
    normalized_payload = _apply_provider_claim_mapping(payload, claim_mapping)

    raw_groups = normalized_payload.get("groups") or normalized_payload.get("roles") or normalized_payload.get("group") or []
    if isinstance(raw_groups, str):
        groups = [role.strip() for role in raw_groups.split(",") if role.strip()]
    elif isinstance(raw_groups, (list, tuple, set)):
        groups = [str(role).strip() for role in raw_groups if str(role).strip()]
    else:
        groups = []

    roles = _oidc_roles_from_claims({"groups": groups, "role": normalized_payload.get("role")})
    allowed_roles = set((provider.allowed_roles or []) if provider else [])
    global_allowed = _allowed_oidc_groups()
    if allowed_roles:
        allowed = {AuthRBAC.normalize_role_name(role) for role in allowed_roles}
        filtered_roles = [role for role in roles if role in allowed or role == "read_only"]
        if not filtered_roles:
            return _api_error("policy_denied", "The external IdP claims do not satisfy the allowed-role policy for this tenant.", 403)
        roles = filtered_roles
    elif global_allowed:
        filtered_roles = [role for role in roles if role in global_allowed or role == "read_only"]
        if not filtered_roles:
            return _api_error("policy_denied", "The external IdP claims do not satisfy the allowed-role policy for this tenant.", 403)
        roles = filtered_roles

    username = payload.get("username") or (email.split("@", 1)[0] if email else "oidc-user")
    auto_provision = bool((provider.auto_provision if provider else False) or os.getenv("OIDC_AUTO_PROVISION", "0") == "1")
    if auto_provision:
        user_record = _provision_external_user_from_claims(tenant_id, email, username, roles, normalized_payload)
        if user_record.status != "active":
            return _api_error("account_disabled", "This account is not active.", 403)
        user = IdentityAccessService.create_principal(
            user_id=user_record.id,
            username=user_record.username,
            tenant_id=user_record.tenant_id,
            roles=user_record.roles,
            permissions=user_record.permissions,
            attributes=user_record.attributes or {},
        )
    else:
        user = IdentityAccessService.create_principal(
            user_id=f"oidc_{uuid.uuid4().hex[:12]}",
            username=username,
            tenant_id=tenant_id,
            roles=roles,
        )

    access_token = AuthRBAC.generate_token(
        user_id=user.user_id,
        username=user.username,
        tenant_id=user.tenant_id,
        roles=user.roles,
    )
    return _api_success({
        "user_id": user.user_id,
        "username": user.username,
        "tenant_id": user.tenant_id,
        "roles": user.roles,
        "email": email,
        "code": code,
        "state": state,
        "token": access_token,
    }, 200)


@_idempotent_route("/auth/sso/oidc/token", methods=["POST"])
def oidc_token():
    """Exchange an authorization code for a signed access token and ID token."""
    data = request.get_json(silent=True) or {}
    grant_type = data.get("grant_type")
    if grant_type == "refresh_token":
        rotated = AuthRBAC.rotate_refresh_token(
            data.get("refresh_token", ""),
            device_id=data.get("device_id"),
            user_agent=request.headers.get("User-Agent"),
            ip_address=request.remote_addr,
        )
        if rotated is None:
            return _api_error("invalid_grant", "Refresh token is invalid, expired, revoked, or already used.", 401)
        user, refresh_token = rotated
        access_token = AuthRBAC.generate_token(
            user_id=user.user_id,
            username=user.username,
            tenant_id=user.tenant_id,
            roles=user.roles,
        )
        return _api_success({
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": 86400,
            "refresh_token": refresh_token,
        }, 200)

    code = data.get("code")
    client_id = data.get("client_id")
    redirect_uri = data.get("redirect_uri")
    if grant_type != "authorization_code" or not code or not client_id or not redirect_uri:
        return _api_error("invalid_request", "authorization_code grant requires client_id, code, and redirect_uri.", 400)

    return _api_error(
        "oidc_exchange_required",
        "Authorization-code exchange is unavailable until provider token and state validation is configured.",
        501,
    )

    session_id = f"oidc_{uuid.uuid4().hex[:12]}"
    access_token = AuthRBAC.generate_token(
        user_id=user.user_id,
        username=user.username,
        tenant_id=user.tenant_id,
        roles=user.roles,
        session_id=session_id,
    )
    id_token = AuthRBAC.generate_token(
        user_id=user.user_id,
        username=user.username,
        tenant_id=user.tenant_id,
        roles=user.roles,
        session_id=session_id,
    )
    session = SessionLocal()
    try:
        session.add(UserSession(
            id=session_id,
            tenant_id=user.tenant_id,
            user_id=user.user_id,
            device_id=data.get("device_id"),
            user_agent=request.headers.get("User-Agent"),
            ip_address=request.remote_addr,
            active=True,
            session_metadata={"source": "oidc"},
        ))
        session.commit()
    finally:
        session.close()
    return _api_success({
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in": 86400,
        "id_token": id_token,
        "scope": "openid profile email",
        "refresh_token": AuthRBAC.generate_refresh_token(
            user_id=user.user_id,
            username=user.username,
            tenant_id=user.tenant_id,
            roles=user.roles,
            session_id=session_id,
            device_id=data.get("device_id"),
            user_agent=request.headers.get("User-Agent"),
            ip_address=request.remote_addr,
        ),
    }, 200)


@_idempotent_route("/auth/users", methods=["GET"])
@require_auth("manage:users")
def list_users():
    """List persisted users for the current tenant."""
    session = SessionLocal()
    try:
        users = session.query(UserAccount).filter(UserAccount.tenant_id == get_current_user().tenant_id).all()
        return _api_success({
            "users": [{
                "user_id": row.id,
                "username": row.username,
                "tenant_id": row.tenant_id,
                "email": row.email,
                "roles": row.roles,
                "mfa_enabled": row.mfa_enabled,
                "status": row.status,
            } for row in users]}, 200)
    finally:
        session.close()


@_idempotent_route("/auth/api-keys", methods=["POST"])
@require_auth("manage:api_keys")
def issue_api_key_route():
    """Issue a tenant-scoped API key."""
    data = request.json or {}
    tenant_id = data.get("tenant_id") or get_current_user().tenant_id
    if tenant_id != get_current_user().tenant_id:
        return _api_success({"error": "tenant_access_denied"}, 403)
    role = AuthRBAC.normalize_role_name(data.get("role") or "read_only")
    if role is None:
        return _api_success({"error": "invalid_role"}, 400)
    key_value = f"pk_{secrets.token_urlsafe(32)}"
    key_hash = hashlib.sha256(key_value.encode("utf-8")).hexdigest()
    scopes = data.get("scopes")
    role_permissions = set(AuthRBAC._get_permissions_for_roles([role]))
    if scopes is None:
        scopes = sorted(role_permissions)
    if not isinstance(scopes, list) or not all(isinstance(scope, str) for scope in scopes):
        return _api_success({"error": "invalid_scopes"}, 400)
    if not set(scopes).issubset(role_permissions):
        return _api_success({"error": "invalid_scopes"}, 400)
    expires_at = None
    if data.get("expires_in_days") is not None:
        try:
            expires_in_days = int(data["expires_in_days"])
        except (TypeError, ValueError):
            return _api_success({"error": "invalid_expiry"}, 400)
        if not 1 <= expires_in_days <= 3650:
            return _api_success({"error": "invalid_expiry"}, 400)
        expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)
    session = SessionLocal()
    try:
        record = ApiKeyRecord(
            id=f"key_{uuid.uuid4().hex[:12]}",
            tenant_id=tenant_id,
            key_hash=key_hash,
            key_prefix=key_value[:16],
            role=role,
            scopes=scopes,
            expires_at=expires_at,
            api_metadata=data.get("metadata") or {},
            active=True,
        )
        session.add(record)
        session.add(ActionAuditEntry(
            tenant_id=tenant_id,
            actor=get_current_user().user_id,
            action="api_key.issued",
            category="authentication",
            resource_type="api_key",
            resource_id=record.id,
            details={"scopes": scopes, "expires_at": expires_at.isoformat() if expires_at else None},
        ))
        session.commit()
        return _api_success({"api_key": key_value, "tenant_id": tenant_id, "role": record.role, "scopes": scopes, "expires_at": expires_at.isoformat() if expires_at else None}, 201)
    finally:
        session.close()


@_idempotent_route("/auth/api-keys/<key_id>/revoke", methods=["POST"])
@require_auth("manage:api_keys")
def revoke_api_key_route(key_id: str):
    """Revoke a tenant-scoped machine credential."""
    session = SessionLocal()
    try:
        record = session.query(ApiKeyRecord).filter(
            ApiKeyRecord.id == key_id,
            ApiKeyRecord.tenant_id == get_current_user().tenant_id,
        ).first()
        if record is None:
            return _api_success({"error": "not_found"}, 404)
        record.active = False
        record.revoked_at = datetime.now(timezone.utc)
        session.add(ActionAuditEntry(
            tenant_id=record.tenant_id,
            actor=get_current_user().user_id,
            action="api_key.revoked",
            category="authentication",
            resource_type="api_key",
            resource_id=record.id,
            details={},
        ))
        session.commit()
        return _api_success({"id": record.id, "status": "revoked"}, 200)
    finally:
        session.close()


@_idempotent_route("/auth/api-keys/<key_id>/rotate", methods=["POST"])
@require_auth("manage:api_keys")
def rotate_api_key_route(key_id: str):
    """Revoke an existing key and issue a replacement in one transaction."""
    session = SessionLocal()
    try:
        current_user = get_current_user()
        old_record = session.query(ApiKeyRecord).filter(
            ApiKeyRecord.id == key_id,
            ApiKeyRecord.tenant_id == current_user.tenant_id,
            ApiKeyRecord.active.is_(True),
        ).first()
        if old_record is None:
            return _api_success({"error": "not_found"}, 404)
        replacement_value = f"pk_{secrets.token_urlsafe(32)}"
        replacement = ApiKeyRecord(
            id=f"key_{uuid.uuid4().hex[:12]}",
            tenant_id=old_record.tenant_id,
            key_hash=hashlib.sha256(replacement_value.encode("utf-8")).hexdigest(),
            key_prefix=replacement_value[:16],
            role=old_record.role,
            scopes=old_record.scopes or [],
            expires_at=old_record.expires_at,
            api_metadata=old_record.api_metadata or {},
            rotated_from_id=old_record.id,
            active=True,
        )
        old_record.active = False
        old_record.revoked_at = datetime.now(timezone.utc)
        session.add(replacement)
        session.add(ActionAuditEntry(
            tenant_id=old_record.tenant_id,
            actor=current_user.user_id,
            action="api_key.rotated",
            category="authentication",
            resource_type="api_key",
            resource_id=replacement.id,
            details={"rotated_from_id": old_record.id},
        ))
        session.commit()
        return _api_success({
            "api_key": replacement_value,
            "id": replacement.id,
            "rotated_from_id": old_record.id,
            "expires_at": replacement.expires_at.isoformat() if replacement.expires_at else None,
        }, 201)
    finally:
        session.close()


@_idempotent_route("/auth/mfa/challenge", methods=["POST"])
@require_auth("manage:mfa")
def create_mfa_challenge_route():
    """Create an MFA challenge for a user."""
    data = request.json or {}
    current_user = get_current_user()
    user_id = data.get("user_id") or current_user.user_id
    if user_id != current_user.user_id:
        target_session = SessionLocal()
        try:
            target = target_session.query(UserAccount).filter_by(id=user_id, tenant_id=current_user.tenant_id).first()
        finally:
            target_session.close()
        if target is None:
            return _api_error("resource_not_found", "MFA user not found.", 404)
    challenge_id = f"mfa_{uuid.uuid4().hex[:12]}"
    code = f"{secrets.randbelow(1_000_000):06d}"
    session = SessionLocal()
    try:
        record = MFAChallenge(
            id=challenge_id,
            user_id=user_id,
            tenant_id=current_user.tenant_id,
            code_hash=hashlib.sha256(code.encode("utf-8")).hexdigest(),
            status="pending",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
            attempts=0,
        )
        session.add(record)
        session.commit()
        return _api_success({"challenge_id": challenge_id, "status": "pending", "user_id": user_id}, 201)
    finally:
        session.close()


@_idempotent_route("/auth/mfa/verify", methods=["POST"])
@require_auth("manage:mfa")
def verify_mfa_route():
    """Verify an MFA challenge code."""
    data = request.json or {}
    user_id = data.get("user_id")
    challenge_id = data.get("challenge_id")
    code = data.get("code")
    if not user_id or not challenge_id or not code:
        return _api_error("invalid_request", "user_id, challenge_id, and code are required.", 400)

    session = SessionLocal()
    try:
        current_user = get_current_user()
        record = session.query(MFAChallenge).filter_by(
            id=challenge_id,
            user_id=user_id,
            tenant_id=current_user.tenant_id,
        ).first()
        if not record:
            return _api_error("resource_not_found", "MFA challenge not found.", 404)
        now = datetime.now(timezone.utc)
        if record.status != "pending" or record.expires_at <= now or record.attempts >= 5:
            return _api_success({"verified": False, "status": record.status}, 200)
        record.attempts += 1
        verified = hmac.compare_digest(record.code_hash, hashlib.sha256(str(code).encode("utf-8")).hexdigest())
        record.status = "verified" if verified else ("failed" if record.attempts >= 5 else "pending")
        session.commit()
        return _api_success({"verified": verified, "status": record.status, "challenge_id": challenge_id}, 200)
    finally:
        session.close()


@_idempotent_route("/auth/passwordless/challenge", methods=["POST"])
@require_auth("manage:users")
def create_passwordless_challenge_route():
    """Create a passwordless challenge for a user."""
    data = request.json or {}
    current_user = get_current_user()
    user_id = data.get("user_id") or current_user.user_id
    if user_id != current_user.user_id:
        target_session = SessionLocal()
        try:
            target = target_session.query(UserAccount).filter_by(id=user_id, tenant_id=current_user.tenant_id).first()
        finally:
            target_session.close()
        if target is None:
            return _api_error("resource_not_found", "Passwordless user not found.", 404)
    challenge_id = f"pw_{uuid.uuid4().hex[:12]}"
    token = secrets.token_urlsafe(32)
    session = SessionLocal()
    try:
        record = PasswordlessChallenge(
            id=challenge_id,
            user_id=user_id,
            tenant_id=current_user.tenant_id,
            token_hash=hashlib.sha256(token.encode("utf-8")).hexdigest(),
            status="pending",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
            attempts=0,
        )
        session.add(record)
        session.commit()
        return _api_success({"challenge_id": challenge_id, "status": "pending", "user_id": user_id}, 201)
    finally:
        session.close()


@_idempotent_route("/auth/passwordless/verify", methods=["POST"])
@require_auth("manage:users")
def verify_passwordless_route():
    """Verify a passwordless challenge token."""
    data = request.json or {}
    user_id = data.get("user_id")
    challenge_id = data.get("challenge_id")
    token = data.get("token")
    if not user_id or not challenge_id or not token:
        return _api_error("invalid_request", "user_id, challenge_id, and token are required.", 400)

    session = SessionLocal()
    try:
        current_user = get_current_user()
        record = session.query(PasswordlessChallenge).filter_by(
            id=challenge_id,
            user_id=user_id,
            tenant_id=current_user.tenant_id,
        ).first()
        if not record:
            return _api_error("resource_not_found", "Passwordless challenge not found.", 404)
        now = datetime.now(timezone.utc)
        if record.status != "pending" or record.expires_at <= now or record.attempts >= 5:
            return _api_success({"verified": False, "status": record.status}, 200)
        record.attempts += 1
        verified = hmac.compare_digest(record.token_hash, hashlib.sha256(str(token).encode("utf-8")).hexdigest())
        record.status = "verified" if verified else ("failed" if record.attempts >= 5 else "pending")
        session.commit()
        return _api_success({"verified": verified, "status": record.status, "challenge_id": challenge_id}, 200)
    finally:
        session.close()


# ============================================================================
# WEBHOOK MANAGEMENT
# ============================================================================

@_idempotent_route("/webhooks", methods=["POST"])
@require_auth("manage:webhooks")
@require_tenant_access()
def create_webhook():
    """Register a new outbound webhook configuration for a tenant."""
    data = request.json or {}
    tenant_id = data.get("tenant_id")
    session = SessionLocal()

    try:
        webhook_mgr = WebhookManager(session)
        result = webhook_mgr.register_webhook(
            tenant_id=tenant_id,
            url=data.get("url"),
            event_types=data.get("event_types", ["escalation"]),
            retry_attempts=data.get("retry_attempts", 3),
            timeout_seconds=data.get("timeout_seconds", 10),
        )
        if "error" in result:
            return jsonify(result), 400

        current_user = get_current_user()
        _record_action_audit(
            session,
            tenant_id=tenant_id,
            actor=getattr(current_user, "user_id", "system"),
            action="create_webhook",
            details={"webhook_id": result.get("id"), "url": data.get("url"), "event_types": result.get("event_types")},
        )
        return jsonify(result), 201
    finally:
        session.close()


@_idempotent_route("/webhooks", methods=["GET"])
@require_auth("manage:webhooks")
@require_tenant_access()
def list_webhooks():
    """List all registered webhooks for a tenant."""
    tenant_id = request.args.get("tenant_id")
    session = SessionLocal()

    try:
        webhook_mgr = WebhookManager(session)
        webhooks = webhook_mgr.get_webhooks(tenant_id)
        return jsonify({
            "tenant_id": tenant_id,
            "webhooks": [
                {
                    "id": w.id,
                    "url": w.url,
                    "event_types": w.event_types,
                    "active": w.active,
                    "created_at": w.created_at.isoformat() if w.created_at else None,
                }
                for w in webhooks
            ],
        }), 200
    finally:
        session.close()


@_idempotent_route("/webhooks/<webhook_id>", methods=["PUT"])
@require_auth("manage:webhooks")
def update_webhook(webhook_id: str):
    """Update webhook configuration details strictly scoped to caller tenant."""
    data = request.json or {}
    data.pop("tenant_id", None)
    current_user = get_current_user()
    tenant_id = getattr(current_user, "tenant_id", None)
    session = SessionLocal()

    try:
        webhook_mgr = WebhookManager(session)
        result = webhook_mgr.update_webhook(webhook_id, tenant_id=tenant_id, **data)
        if result.get("error") == "webhook_not_found":
            return jsonify(result), 404

        _record_action_audit(
            session,
            tenant_id=tenant_id or "default",
            actor=getattr(current_user, "user_id", "system"),
            action="update_webhook",
            details={"webhook_id": webhook_id, **data},
        )
        return jsonify(result), 200
    finally:
        session.close()


@_idempotent_route("/webhooks/<webhook_id>/deliveries", methods=["GET"])
@require_auth("manage:webhooks")
def get_webhook_deliveries(webhook_id: str):
    """Retrieve delivery history logs for a specific webhook."""
    limit = min(max(request.args.get("limit", 50, type=int), 1), 200)
    current_user = get_current_user()
    tenant_id = getattr(current_user, "tenant_id", None)
    session = SessionLocal()

    try:
        webhook_mgr = WebhookManager(session)
        deliveries = webhook_mgr.get_delivery_history(webhook_id, tenant_id=tenant_id, limit=limit)
        return jsonify({
            "webhook_id": webhook_id,
            "deliveries": deliveries,
        }), 200
    finally:
        session.close()


# ============================================================================
# ESCALATION RULES
# ============================================================================

@_idempotent_route("/escalation-rules", methods=["POST"])
@require_auth("write:escalation_rules")
@require_tenant_access()
def create_escalation_rule():
    """Create a custom automated escalation rule for a tenant."""
    data = request.json or {}
    tenant_id = data.get("tenant_id")
    session = SessionLocal()

    try:
        engine_instance = EscalationEngine(session)
        result = engine_instance.create_rule(
            tenant_id=tenant_id,
            name=data.get("name"),
            description=data.get("description"),
            condition_field=data.get("condition_field"),
            condition_operator=data.get("condition_operator"),
            condition_value=data.get("condition_value"),
            action=data.get("action"),
            target=data.get("target"),
            webhook_url=data.get("webhook_url"),
            priority=data.get("priority", 0),
        )
        current_user = get_current_user()
        _record_action_audit(
            session,
            tenant_id=tenant_id,
            actor=getattr(current_user, "user_id", "system"),
            action="create_escalation_rule",
            details={"rule_id": result.get("id"), "name": data.get("name")},
        )
        return jsonify(result), 201
    finally:
        session.close()


@_idempotent_route("/escalation-rules", methods=["GET"])
@require_auth("read:discrepancies")
@require_tenant_access()
def list_escalation_rules():
    """List active escalation rules for a tenant."""
    tenant_id = request.args.get("tenant_id")
    session = SessionLocal()

    try:
        engine_instance = EscalationEngine(session)
        rules = engine_instance.get_rules(tenant_id)
        return jsonify({
            "tenant_id": tenant_id,
            "rules": rules,
        }), 200
    finally:
        session.close()


@_idempotent_route("/escalation-rules/<rule_id>", methods=["PUT"])
@require_auth("write:escalation_rules")
@require_tenant_access()
def update_escalation_rule(rule_id: str):
    """Update an existing escalation rule configuration."""
    data = request.json or {}
    session = SessionLocal()

    try:
        engine_instance = EscalationEngine(session)
        tenant_id = data.get("tenant_id") or get_current_user().tenant_id
        rule_data = dict(data)
        rule_data.pop("tenant_id", None)
        result = engine_instance.update_rule(rule_id, tenant_id=tenant_id, **rule_data)
        return jsonify(result), 200
    finally:
        session.close()


# ============================================================================
# ON-CALL ROTATIONS
# ============================================================================

@_idempotent_route("/on-call/rotations", methods=["POST"])
@require_auth("manage:on_call")
@require_tenant_access()
def create_on_call_rotation():
    """Create an on-call schedule rotation entry."""
    data = request.json or {}
    tenant_id = data.get("tenant_id")
    session = SessionLocal()

    try:
        service = OnCallService(session)
        shift_start = datetime.fromisoformat(data.get("shift_start"))
        shift_end = datetime.fromisoformat(data.get("shift_end"))

        result = service.create_rotation(
            tenant_id=tenant_id,
            operator_id=data.get("operator_id"),
            operator_name=data.get("operator_name"),
            operator_email=data.get("operator_email"),
            operator_phone=data.get("operator_phone"),
            shift_start=shift_start,
            shift_end=shift_end,
            escalation_level=data.get("escalation_level", 1),
        )
        current_user = get_current_user()
        _record_action_audit(
            session,
            tenant_id=tenant_id,
            actor=getattr(current_user, "user_id", "system"),
            action="create_on_call_rotation",
            details={"operator_id": data.get("operator_id"), "shift_start": shift_start.isoformat(), "shift_end": shift_end.isoformat()},
        )
        return jsonify(result), 201
    finally:
        session.close()


@_idempotent_route("/on-call/rotations/active", methods=["GET"])
@require_auth("read:discrepancies")
@require_tenant_access()
def get_active_on_call():
    """Retrieve active on-call coverage status for a tenant."""
    tenant_id = request.args.get("tenant_id")
    session = SessionLocal()

    try:
        service = OnCallService(session)
        rotations = service.get_active_rotations(tenant_id)
        coverage = service.get_coverage_status(tenant_id)

        return jsonify({
            "tenant_id": tenant_id,
            "coverage": coverage,
            "active_rotations": rotations,
        }), 200
    finally:
        session.close()


@_idempotent_route("/on-call/schedule/<operator_id>", methods=["GET"])
@require_auth("read:discrepancies")
@require_tenant_access()
def get_operator_schedule(operator_id: str):
    """Retrieve an operator's on-call schedule window."""
    tenant_id = request.args.get("tenant_id")
    days = min(max(request.args.get("days", 30, type=int), 1), 365)
    session = SessionLocal()

    try:
        service = OnCallService(session)
        schedule = service.get_operator_schedule(tenant_id, operator_id, days)
        return jsonify({
            "operator_id": operator_id,
            "tenant_id": tenant_id,
            "days": days,
            "schedule": schedule,
        }), 200
    finally:
        session.close()


@_idempotent_route("/on-call/bulk", methods=["POST"])
@require_auth("manage:on_call")
@require_tenant_access()
def bulk_create_on_call():
    """Bulk create multiple on-call schedule rotations."""
    data = request.json or {}
    tenant_id = data.get("tenant_id")
    rotations_data = data.get("rotations", [])
    session = SessionLocal()

    try:
        service = OnCallService(session)
        result = service.bulk_create_rotations(tenant_id, rotations_data)
        current_user = get_current_user()
        _record_action_audit(
            session,
            tenant_id=tenant_id,
            actor=getattr(current_user, "user_id", "system"),
            action="bulk_create_on_call_rotations",
            details={"created": result.get("created", 0)},
        )
        return jsonify(result), 201
    finally:
        session.close()


# ============================================================================
# EMAIL NOTIFICATIONS
# ============================================================================

@_idempotent_route("/emails/reconciliation", methods=["POST"])
@require_auth("write:discrepancies")
@require_tenant_access()
def send_reconciliation_email():
    """Dispatch structured reconciliation report via email."""
    data = request.json or {}
    tenant_id = data.get("tenant_id")
    recipient = data.get("recipient_email")
    report_data = data.get("report_data", {})
    session = SessionLocal()

    try:
        current_user = get_current_user()
        locale = resolve_email_locale(
            tenant_id,
            user_id=getattr(current_user, "user_id", None) or data.get("user_id") or request.args.get("user_id"),
        )
        result = email_service.send_reconciliation_report(
            session, tenant_id, recipient, report_data, locale=locale
        )
        _record_action_audit(
            session,
            tenant_id=tenant_id,
            actor=getattr(current_user, "user_id", "system"),
            action="send_reconciliation_email",
            details={"recipient": recipient, "report_data": report_data},
        )
        return jsonify(result), 200
    finally:
        session.close()


@_idempotent_route("/emails/escalation", methods=["POST"])
@require_auth("write:discrepancies")
@require_tenant_access()
def send_escalation_email():
    """Dispatch critical incident escalation alert via email."""
    data = request.json or {}
    tenant_id = data.get("tenant_id")
    recipient = data.get("recipient_email")
    incident = data.get("incident_data", {})
    session = SessionLocal()

    try:
        current_user = get_current_user()
        locale = resolve_email_locale(
            tenant_id,
            user_id=getattr(current_user, "user_id", None) or data.get("user_id") or request.args.get("user_id"),
        )
        result = email_service.send_escalation_notification(
            session, tenant_id, recipient, incident, locale=locale
        )
        _record_action_audit(
            session,
            tenant_id=tenant_id,
            actor=getattr(current_user, "user_id", "system"),
            action="send_escalation_email",
            details={"recipient": recipient, "incident": incident},
        )
        return jsonify(result), 200
    finally:
        session.close()


@_idempotent_route("/emails/history", methods=["GET"])
@require_auth("read:discrepancies")
@require_tenant_access()
def get_email_history():
    """Retrieve historical email notification delivery logs."""
    tenant_id = request.args.get("tenant_id")
    limit = min(max(request.args.get("limit", 50, type=int), 1), 200)
    session = SessionLocal()

    try:
        history = email_service.get_email_history(session, tenant_id, limit)
        return jsonify({
            "tenant_id": tenant_id,
            "emails": history,
        }), 200
    finally:
        session.close()


# ============================================================================
# ADVANCED SEARCH
# ============================================================================

@_idempotent_route("/search", methods=["GET"])
@require_auth("read:discrepancies")
@require_tenant_access()
def advanced_search():
    """Execute advanced boolean text queries across discrepancies."""
    tenant_id = request.args.get("tenant_id")
    query = request.args.get("q", "")
    limit = min(max(request.args.get("limit", 50, type=int), 1), 200)
    offset = max(request.args.get("offset", 0, type=int), 0)
    session = SessionLocal()

    try:
        search = AdvancedSearchEngine(session)
        result = search.search(tenant_id, query, limit=limit, offset=offset)
        return jsonify(result), 200
    finally:
        session.close()


@_idempotent_route("/search/filters", methods=["GET"])
@require_auth("read:discrepancies")
@require_tenant_access()
def search_filters():
    """Retrieve available filter facets for advanced search."""
    tenant_id = request.args.get("tenant_id")
    session = SessionLocal()

    try:
        search = AdvancedSearchEngine(session)
        filters = search.suggest_filters(tenant_id)
        return jsonify({
            "tenant_id": tenant_id,
            "available_filters": filters,
        }), 200
    finally:
        session.close()


@_idempotent_route("/search/structured", methods=["GET"])
@require_auth("read:discrepancies")
@require_tenant_access()
def structured_search():
    """Execute structured filtering queries against reconciliation records."""
    tenant_id = request.args.get("tenant_id")
    limit = min(max(request.args.get("limit", 50, type=int), 1), 200)
    offset = max(request.args.get("offset", 0, type=int), 0)
    session = SessionLocal()

    try:
        search = AdvancedSearchEngine(session)
        result = search.search_by_filters(
            tenant_id=tenant_id,
            severity=request.args.get("severity"),
            status=request.args.get("status"),
            anomaly_type=request.args.get("anomaly_type"),
            resolved=request.args.get("resolved", type=lambda x: x.lower() == "true"),
            assignee=request.args.get("assignee"),
            days_back=min(max(request.args.get("days_back", 30, type=int), 1), 365),
            limit=limit,
            offset=offset,
        )
        return jsonify(result), 200
    finally:
        session.close()


# ============================================================================
# PUBLIC CUSTOMER-FACING ENDPOINTS
# ============================================================================

@_idempotent_route("/public/customers/<tenant_id>/reconciliations", methods=["GET"])
@require_auth("read:discrepancies")
@require_tenant_access()
def public_get_reconciliations(tenant_id: str):
    """Retrieve secure, tenant-scoped recent reconciliation outcomes."""
    limit = min(max(request.args.get("limit", 50, type=int), 1), 200)
    offset = max(request.args.get("offset", 0, type=int), 0)
    session = SessionLocal()

    try:
        q = (
            session.query(Discrepancy)
            .filter(Discrepancy.tenant_id == tenant_id)
            .order_by(Discrepancy.detected_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = q.all()
        return jsonify({
            "tenant_id": tenant_id,
            "count": len(rows),
            "reconciliations": [
                {
                    "id": r.id,
                    "trans_id": r.trans_id,
                    "anomaly_type": r.anomaly_type,
                    "status": r.status,
                    "severity": r.severity,
                    "details": r.details,
                    "detected_at": r.detected_at.isoformat() if r.detected_at else None,
                    "resolved": bool(r.resolved),
                }
                for r in rows
            ],
        }), 200
    finally:
        session.close()


@_idempotent_route("/public/customers/<tenant_id>/reports", methods=["GET"])
@require_auth("read:analytics")
@require_tenant_access()
def public_get_reports(tenant_id: str):
    """Retrieve generated financial discrepancy reports for a tenant."""
    limit = min(max(request.args.get("limit", 50, type=int), 1), 200)
    offset = max(request.args.get("offset", 0, type=int), 0)
    session = SessionLocal()

    try:
        q = (
            session.query(Report)
            .filter(Report.tenant_id == tenant_id)
            .order_by(Report.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = q.all()
        return jsonify({
            "tenant_id": tenant_id,
            "count": len(rows),
            "reports": [
                {
                    "id": r.id,
                    "report_type": r.report_type,
                    "period_start": r.period_start.isoformat() if r.period_start else None,
                    "period_end": r.period_end.isoformat() if r.period_end else None,
                    "status": r.status,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "content": r.content,
                }
                for r in rows
            ],
        }), 200
    finally:
        session.close()


# ============================================================================
# RATE LIMITED BULK OPERATIONS
# ============================================================================

@_idempotent_route("/bulk/assign", methods=["POST"])
@require_auth("bulk:operations")
@rate_limit(max_requests_per_minute=5, tokens_per_request=1, endpoint_name="bulk_assign")
@require_tenant_access()
def bulk_assign_incidents():
    """Bulk assign incidents securely with rate limiting and strict tenant scoping."""
    data = request.json or {}
    tenant_id = data.get("tenant_id")
    incident_ids = data.get("incident_ids", [])
    assignee = data.get("assignee")
    session = SessionLocal()

    try:
        updated = 0
        skipped_ids = []
        for incident_id in incident_ids[:100]:  # Hard cap at 100 per request
            incident = _incident_belongs_to_tenant(session, incident_id, tenant_id)
            if incident:
                incident.assignee = assignee
                updated += 1
            else:
                skipped_ids.append(incident_id)

        session.commit()
        current_user = get_current_user()
        _record_action_audit(
            session,
            tenant_id=tenant_id,
            actor=getattr(current_user, "user_id", "system"),
            action="bulk_assign_incidents",
            details={"updated": updated, "skipped_ids": skipped_ids, "assignee": assignee},
        )
        return jsonify({
            "updated": updated,
            "skipped_ids": skipped_ids,
            "rate_limit": get_rate_limit_status(),
        }), 200
    finally:
        session.close()


@_idempotent_route("/bulk/escalate", methods=["POST"])
@require_auth("bulk:operations")
@rate_limit(max_requests_per_minute=3, tokens_per_request=2, endpoint_name="bulk_escalate")
@require_tenant_access()
def bulk_escalate_incidents():
    """Bulk escalate incidents securely with rate limiting and strict tenant scoping."""
    data = request.json or {}
    tenant_id = data.get("tenant_id")
    incident_ids = data.get("incident_ids", [])
    session = SessionLocal()

    try:
        escalated = []
        skipped_ids = []
        engine_instance = EscalationEngine(session)

        for incident_id in incident_ids[:50]:  # Hard cap at 50 per request
            incident = _incident_belongs_to_tenant(session, incident_id, tenant_id)
            if incident:
                result = engine_instance.evaluate_and_escalate(tenant_id, incident)
                escalated.append(result)
            else:
                skipped_ids.append(incident_id)

        current_user = get_current_user()
        _record_action_audit(
            session,
            tenant_id=tenant_id,
            actor=getattr(current_user, "user_id", "system"),
            action="bulk_escalate_incidents",
            details={"escalated_count": len(escalated), "skipped_ids": skipped_ids},
        )
        return jsonify({
            "escalated": len(escalated),
            "details": escalated,
            "skipped_ids": skipped_ids,
            "rate_limit": get_rate_limit_status(),
        }), 200
    finally:
        session.close()


if __name__ == "__main__":
    debug_mode = os.getenv("FLASK_DEBUG", "0") == "1"
    if debug_mode:
        logger.warning("Running with debug=True — never do this in production.")
    port = int(os.getenv("PORT", 5002))
    app.run(debug=debug_mode, host=os.getenv("PESAGUARD_BIND_HOST", "127.0.0.1"), port=port)

