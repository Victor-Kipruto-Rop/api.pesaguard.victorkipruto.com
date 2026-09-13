"""Robust M-Pesa webhook ingestion gateway for PesaGuard with rate limiting and verification."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

import redis
from flask import Flask, Response, abort, jsonify, request
from werkzeug.exceptions import HTTPException

from observability import init_sentry

from background_tasks import enqueue_transaction_outbox_drain
from event_store import EventStore, ProcessResult, provider_account_id
from health import build_health_payload
from idempotency import derive_idempotency_key
from logging_utils import configure_logging, get_correlation_id, set_correlation_id
from metrics import build_metrics_payload
from rate_limiter import RateLimiter
from security_helpers import (
    get_client_ip,
    is_allowed_source,
    is_payload_within_limit,
    sanitize_error_message,
)
from shared.daraja.validator import validate_daraja_callback
from tenant_settings import TenantSettingsStore
from validators import validate_daraja_payload
from auth_rbac import AuthRBAC, get_current_user, require_auth

configure_logging()
logger = logging.getLogger("pesaguard.webhook")

app = Flask(__name__)
init_sentry(service="webhook", provider="mpesa")
app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("PESAGUARD_WEBHOOK_MAX_BODY_BYTES", "1048576"))

event_store = EventStore()
webhook_rate_limiter = RateLimiter()
webhook_rate_limiter.set_limits(int(os.getenv("PESAGUARD_WEBHOOK_RATE_LIMIT_PER_MINUTE", "30")))

tenant_store = TenantSettingsStore()


def _require_admin() -> None:
    """Enforce admin token authentication on sensitive configuration endpoints."""
    token = request.headers.get("X-Admin-Token")
    admin_api_token = os.getenv("PESAGUARD_ADMIN_API_TOKEN")
    if not admin_api_token or token != admin_api_token:
        abort(403)


@app.route("/admin/tenant/<tenant_id>", methods=["GET"])
def admin_get_tenant(tenant_id: str):
    _require_admin()
    return jsonify(tenant_store.get(tenant_id)), 200


@app.route("/admin/tenant/<tenant_id>", methods=["POST"])
def admin_update_tenant(tenant_id: str):
    _require_admin()
    payload = request.get_json(silent=True) or {}
    updated = tenant_store.update(tenant_id, payload)
    return jsonify(updated), 200


@app.route("/admin/tenant/<tenant_id>/residency", methods=["GET"])
def admin_get_residency(tenant_id: str):
    _require_admin()
    return jsonify(tenant_store.get_residency_context(tenant_id)), 200


@app.route("/admin/tenant/<tenant_id>/locale", methods=["POST"])
def admin_set_locale(tenant_id: str):
    _require_admin()
    payload = request.get_json(silent=True) or {}
    preferred = payload.get("preferred_locale")
    if not preferred:
        return jsonify({"error": "preferred_locale required"}), 400
    updated = tenant_store.update(tenant_id, {"preferred_locale": preferred})
    return jsonify(updated), 200


@app.route("/tenant/current", methods=["GET"])
@require_auth("read:settings")
def public_get_current_tenant():
    """Public, read-only endpoint returning limited tenant preferences for the current runtime tenant."""
    tenant_id = get_current_user().tenant_id
    settings = tenant_store.get(tenant_id)
    public = {
        "tenant_id": tenant_id,
        "preferred_locale": settings.get("preferred_locale"),
        "deployment_region": settings.get("deployment_region"),
    }
    return jsonify(public), 200


@app.route("/tenant/current/locale", methods=["GET"])
@require_auth("read:settings")
def public_get_current_locale():
    """Return tenant default, optional user override, and effective locale."""
    current_user = get_current_user()
    tenant_id = current_user.tenant_id
    user_id = current_user.user_id
    settings = tenant_store.get(tenant_id)
    user_locale = None
    if user_id:
        overrides = settings.get("user_locale_overrides") or {}
        if isinstance(overrides, dict):
            user_locale = overrides.get(user_id) or overrides.get(str(user_id))
    effective = tenant_store.resolve_locale(tenant_id, user_id)
    return jsonify({
        "tenant_id": tenant_id,
        "preferred_locale": settings.get("preferred_locale"),
        "user_locale": user_locale,
        "effective_locale": effective,
    }), 200


@app.route("/tenant/current/locale", methods=["POST"])
@require_auth("write:settings")
def public_set_current_tenant_locale():
    """Persist the current tenant's preferred locale through the public tenant endpoint."""
    payload = request.get_json(silent=True) or {}
    preferred = payload.get("preferred_locale")
    if not preferred:
        return jsonify({"error": "preferred_locale required"}), 400

    tenant_id = get_current_user().tenant_id
    updated = tenant_store.update(tenant_id, {"preferred_locale": preferred})
    return jsonify({"tenant_id": tenant_id, "preferred_locale": updated.get("preferred_locale")}), 200


@app.route("/tenant/current/user-locale", methods=["POST"])
@require_auth("write:settings")
def public_set_user_locale():
    """Persist a per-user locale override for the current tenant."""
    payload = request.get_json(silent=True) or {}
    user_id = payload.get("user_id")
    preferred = payload.get("preferred_locale")
    if not user_id:
        return jsonify({"error": "user_id required"}), 400

    current_user = get_current_user()
    if str(user_id) != current_user.user_id and not AuthRBAC.check_permission(current_user, "manage:users"):
        return jsonify({"error": "user_access_denied"}), 403
    tenant_id = current_user.tenant_id
    existing = tenant_store.get(tenant_id)
    overrides = dict(existing.get("user_locale_overrides") or {})
    if preferred is None or preferred == "":
        overrides.pop(str(user_id), None)
    else:
        overrides[str(user_id)] = preferred
    tenant_store.update(tenant_id, {"user_locale_overrides": overrides})
    effective = tenant_store.resolve_locale(tenant_id, str(user_id))
    return jsonify({
        "tenant_id": tenant_id,
        "user_id": str(user_id),
        "user_locale": overrides.get(str(user_id)),
        "effective_locale": effective,
    }), 200


@app.errorhandler(413)
def handle_request_too_large(_error):
    return jsonify({"ResultCode": 1, "ResultDesc": "Request body too large"}), 413


@app.errorhandler(400)
def handle_bad_request(_error):
    return jsonify({"ResultCode": 1, "ResultDesc": "Invalid request"}), 400


@app.errorhandler(Exception)
def handle_internal_error(error):
    if isinstance(error, HTTPException):
        return error

    logger.exception("Unhandled exception in webhook receiver", exc_info=error)
    return jsonify({"ResultCode": 1, "ResultDesc": "Internal server error"}), 500


@app.before_request
def setup_request_context():
    """Set up per-request context including correlation ID for tracing."""
    correlation_id = request.headers.get("X-Correlation-ID") or get_correlation_id()
    set_correlation_id(correlation_id)


@app.after_request
def add_correlation_id_header(response):
    """Add correlation ID to response headers for client tracing."""
    correlation_id = get_correlation_id()
    response.headers["X-Correlation-ID"] = correlation_id
    return response


@app.before_request
def enforce_webhook_security():
    if request.method == "OPTIONS":
        return None

    is_webhook_request = (
        request.path in {"/webhook", "/webhook/", "/webhook/mpesa/confirmation", "/webhook/mpesa/validation"}
        or request.path.startswith("/daraja")
        or request.path.startswith("/webhook/")
        or request.headers.get("X-Daraja-Shared-Secret") is not None
        or request.headers.get("X-PesaGuard-Signature") is not None
    )

    if not is_payload_within_limit(
        request,
        max_body_bytes=int(os.getenv("PESAGUARD_WEBHOOK_MAX_BODY_BYTES", "1048576"))
        if is_webhook_request
        else None,
    ):
        return jsonify({"ResultCode": 1, "ResultDesc": "Request body too large"}), 413

    if is_webhook_request:
        client_ip = get_client_ip(request)
        if not is_allowed_source(client_ip, request):
            logger.warning("Webhook request rejected: forbidden source IP", extra={"source_ip": client_ip})
            return jsonify({"ResultCode": 1, "ResultDesc": "Forbidden source"}), 403

        allowed, status = webhook_rate_limiter.is_allowed(
            client_ip,
            request.path,
        )
        if not allowed:
            logger.warning("Webhook request rejected: rate limit exceeded", extra={"source_ip": client_ip})
            response = jsonify({"ResultCode": 1, "ResultDesc": "Rate limit exceeded"})
            response.status_code = 429
            response.headers["Retry-After"] = str(status.get("retry_after", 60))
            return response

        daraja_signature = request.headers.get("X-Daraja-Signature")
        if daraja_signature:
            try:
                _verify_daraja_signature(request.data, daraja_signature)
            except Exception as e:
                logger.warning("Webhook signature verification failed", extra={"error": str(e)})
                return jsonify({"ResultCode": 1, "ResultDesc": "Invalid signature"}), 403


@app.route("/metrics", methods=["GET"])
def metrics():
    return Response(build_metrics_payload(), mimetype="text/plain; version=0.0.4")


def _verify_daraja_signature(request_body: bytes, signature: str) -> None:
    """Verify incoming webhook signature from Daraja using constant-time comparison."""
    consumer_secret = os.getenv("DARAJA_CONSUMER_SECRET", "")
    if not consumer_secret:
        raise ValueError("DARAJA_CONSUMER_SECRET not configured")
    if not validate_daraja_callback(request_body, signature, consumer_secret):
        raise ValueError("Signature mismatch")


@app.route("/health", methods=["GET"])
def health():
    payload = build_health_payload()
    status_code = 200 if payload.get("status") == "ok" else 503
    return jsonify(payload), status_code


@app.route("/webhook/mpesa/confirmation", methods=["POST"])
def mpesa_confirmation():
    """Handles C2B confirmation callbacks from Daraja with strict idempotency and atomicity safeguards."""
    payload = request.get_json(silent=True)
    tenant_id = os.getenv("TENANT_ID", "default")

    if not payload:
        logger.warning("Empty or invalid JSON payload received")
        try:
            event_store.write_dead_letter(None, reason="invalid_json", error_detail="empty_or_invalid_json", tenant_id=tenant_id)
        except Exception:
            logger.debug("Failed to persist dead-letter for invalid JSON payload", exc_info=True)
        return jsonify({"ResultCode": 1, "ResultDesc": "Invalid payload"}), 400

    if not is_payload_within_limit(request):
        return jsonify({"ResultCode": 1, "ResultDesc": "Request body too large"}), 413

    is_valid, error = validate_daraja_payload(payload)
    if not is_valid:
        logger.warning("Payload validation failed: %s", error)
        try:
            event_store.write_dead_letter(payload, reason="validation_failed", error_detail=str(error), tenant_id=tenant_id)
        except Exception:
            logger.debug("Failed to persist dead-letter for validation failure", exc_info=True)
        return jsonify({"ResultCode": 1, "ResultDesc": sanitize_error_message(error)}), 400

    trans_id = payload.get("TransID")
    idempotency_key = derive_idempotency_key(payload)
    account_id = provider_account_id(payload)

    if event_store.already_processed(str(trans_id), tenant_id=tenant_id, provider_account=account_id):
        logger.info(
            "Duplicate transaction (pre-check)",
            extra={"tenant_id": tenant_id, "trans_id": trans_id, "idempotency_key": idempotency_key},
        )
        return jsonify({"ResultCode": 0, "ResultDesc": "Accepted (duplicate ignored)"}), 200

    result = event_store.mark_processed(payload, tenant_id=tenant_id)

    if result == ProcessResult.DUPLICATE:
        logger.info(
            "Duplicate transaction (caught at write time)",
            extra={"tenant_id": tenant_id, "trans_id": trans_id, "idempotency_key": idempotency_key},
        )
        return jsonify({"ResultCode": 0, "ResultDesc": "Accepted (duplicate ignored)"}), 200

    if result == ProcessResult.ERROR:
        logger.error(
            "Failed to record transaction, requesting Daraja retry",
            extra={"tenant_id": tenant_id, "trans_id": trans_id, "idempotency_key": idempotency_key},
        )
        return jsonify({"ResultCode": 1, "ResultDesc": "Temporary processing error, please retry"}), 500

    # Best-effort Redis cache warm: maintain both the canonical idempotency key and
    # the legacy trans-id key expected by older callers and tests.
    try:
        redis_conn = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"), socket_connect_timeout=2)
        cache_key = f"processed:{idempotency_key}"
        legacy_cache_key = f"processed_trans_id:{trans_id}"
        redis_conn.set(cache_key, "1", ex=86400)
        redis_conn.set(legacy_cache_key, "1", ex=86400)
    except Exception:
        pass

    queued = enqueue_transaction_outbox_drain()
    logger.info(
        "Transaction outbox delivery scheduled",
        extra={"trans_id": trans_id, "delivery_status": queued.get("status")},
    )

    return jsonify({"ResultCode": 0, "ResultDesc": "Accepted"}), 200


@app.route("/webhook/mpesa/validation", methods=["POST"])
def mpesa_validation():
    """Handles C2B validation callbacks (pre-confirmation)."""
    payload = request.get_json(silent=True) or {}
    logger.info("Validation request for: %s", payload.get("TransID", "unknown"))
    return jsonify({"ResultCode": 0, "ResultDesc": "Accepted"}), 200


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host=os.getenv("PESAGUARD_BIND_HOST", "127.0.0.1"), port=port)
