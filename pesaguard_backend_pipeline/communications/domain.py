from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import string
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from .core.enums import CommunicationChannel
from .models import CommunicationConsent, CommunicationOtpChallenge, CommunicationPreference, CommunicationTemplate


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def create_template(session: Session, *, tenant_id: str, slug: str, channel: CommunicationChannel, body: str, variables: list[str]) -> CommunicationTemplate:
    latest = session.query(CommunicationTemplate).filter_by(tenant_id=tenant_id, slug=slug).order_by(CommunicationTemplate.version.desc()).first()
    template = CommunicationTemplate(
        id=f"template_{uuid.uuid4().hex}", tenant_id=tenant_id, slug=slug,
        version=(latest.version + 1 if latest else 1), channel=channel.value,
        body=body, variables=variables, status="draft",
    )
    session.add(template)
    session.flush()
    return template


def approve_template(session: Session, template: CommunicationTemplate, approver: str) -> CommunicationTemplate:
    template.status = "approved"
    template.approved_by = approver
    template.approved_at = utc_now()
    session.flush()
    return template


def render_template(template: CommunicationTemplate, values: dict[str, object]) -> str:
    missing = [name for name in (template.variables or []) if name not in values]
    if missing:
        raise ValueError(f"missing template variables: {', '.join(missing)}")
    return template.body.format_map(values)


def set_consent(session: Session, *, tenant_id: str, recipient: str, channel: CommunicationChannel, purpose: str, granted: bool, source: str = "api") -> CommunicationConsent:
    consent = session.query(CommunicationConsent).filter_by(tenant_id=tenant_id, recipient=recipient, channel=channel.value).one_or_none()
    if consent is None:
        consent = CommunicationConsent(id=f"consent_{uuid.uuid4().hex}", tenant_id=tenant_id, recipient=recipient, channel=channel.value, purpose=purpose)
        session.add(consent)
    consent.purpose, consent.granted, consent.source, consent.updated_at = purpose, int(granted), source, utc_now()
    session.flush()
    return consent


def is_allowed_now(preference: CommunicationPreference | None, *, now: datetime | None = None) -> bool:
    if preference is None or not preference.quiet_hours_start or not preference.quiet_hours_end:
        return True
    current = (now or utc_now()).astimezone(ZoneInfo(preference.timezone)).strftime("%H:%M")
    start, end = preference.quiet_hours_start, preference.quiet_hours_end
    return not (start <= current < end if start < end else current >= start or current < end)


def _otp_pepper() -> str:
    pepper = os.getenv("PESAGUARD_OTP_HASH_PEPPER", "")
    if not pepper:
        # Deterministic development fallback; production must configure a pepper.
        pepper = "pesaguard-dev-otp-pepper"
    return pepper


def _hash_otp(code: str) -> str:
    return hmac.new(_otp_pepper().encode("utf-8"), code.encode("utf-8"), hashlib.sha256).hexdigest()


def _env_int(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, str(default))))
    except ValueError:
        return default


class OtpRateLimited(ValueError):
    """Raised when OTP issuance exceeds configured abuse thresholds."""

    def __init__(self, message: str, *, reason: str, retry_after_seconds: int = 60):
        super().__init__(message)
        self.reason = reason
        self.retry_after_seconds = retry_after_seconds


def issue_otp(
    session: Session,
    *,
    tenant_id: str,
    recipient: str,
    purpose: str,
    ttl_seconds: int | None = None,
    ip_address: str | None = None,
    context: dict | None = None,
    risk_level: str = "normal",
    now: datetime | None = None,
) -> tuple[CommunicationOtpChallenge, str]:
    """Issue a hardened OTP with cooldown, rate limits, and risk-based policy.

    Risk-based policy: `normal` login -> 6 digits / default TTL; `elevated`
    (suspicious login) -> shorter TTL, fewer attempts, longer cooldown.
    """
    now = now or utc_now()
    cooldown = _env_int("PESAGUARD_OTP_RESEND_COOLDOWN_SECONDS", 60)
    recipient_hourly = _env_int("PESAGUARD_OTP_RECIPIENT_HOURLY_LIMIT", 5)
    ip_hourly = _env_int("PESAGUARD_OTP_IP_HOURLY_LIMIT", 20)
    if risk_level == "elevated":
        cooldown = max(cooldown, _env_int("PESAGUARD_OTP_ELEVATED_COOLDOWN_SECONDS", 120))
        ttl_seconds = min(ttl_seconds or 120, 120)
        max_attempts = 3
    else:
        ttl_seconds = ttl_seconds or _env_int("PESAGUARD_OTP_TTL_SECONDS", 300)
        max_attempts = _env_int("PESAGUARD_OTP_MAX_ATTEMPTS", 5)

    window_start = now - timedelta(hours=1)

    last = (
        session.query(CommunicationOtpChallenge)
        .filter_by(tenant_id=tenant_id, recipient=recipient)
        .order_by(CommunicationOtpChallenge.created_at.desc())
        .first()
    )
    if last is not None and last.created_at:
        last_created = last.created_at if last.created_at.tzinfo else last.created_at.replace(tzinfo=timezone.utc)
        elapsed = (now - last_created).total_seconds()
        if elapsed < cooldown:
            raise OtpRateLimited(
                "otp resend cooldown is active for this recipient",
                reason="resend_cooldown",
                retry_after_seconds=int(cooldown - elapsed) + 1,
            )

    recipient_count = (
        session.query(CommunicationOtpChallenge)
        .filter(
            CommunicationOtpChallenge.tenant_id == tenant_id,
            CommunicationOtpChallenge.recipient == recipient,
            CommunicationOtpChallenge.created_at >= window_start,
        )
        .count()
    )
    if recipient_count >= recipient_hourly:
        raise OtpRateLimited(
            "otp request limit reached for this recipient",
            reason="recipient_rate_limited",
            retry_after_seconds=3600,
        )

    if ip_address:
        ip_count = (
            session.query(CommunicationOtpChallenge)
            .filter(
                CommunicationOtpChallenge.tenant_id == tenant_id,
                CommunicationOtpChallenge.ip_address == ip_address,
                CommunicationOtpChallenge.created_at >= window_start,
            )
            .count()
        )
        if ip_count >= ip_hourly:
            raise OtpRateLimited(
                "otp request limit reached for this network",
                reason="ip_rate_limited",
                retry_after_seconds=3600,
            )

    code = "".join(secrets.choice(string.digits) for _ in range(6))
    challenge = CommunicationOtpChallenge(
        id=f"otp_{uuid.uuid4().hex}",
        tenant_id=tenant_id,
        recipient=recipient,
        purpose=purpose,
        code_hash=_hash_otp(code),
        max_attempts=max_attempts,
        ip_address=ip_address,
        context_json=dict(context or {}),
        expires_at=now + timedelta(seconds=ttl_seconds),
        created_at=now,
    )
    session.add(challenge)
    session.flush()
    return challenge, code


def verify_otp(session: Session, challenge: CommunicationOtpChallenge, code: str, *, now: datetime | None = None) -> bool:
    now = now or utc_now()
    if challenge.consumed_at or challenge.expires_at <= now or challenge.attempts >= challenge.max_attempts:
        try:
            from metrics import record_security_event
            record_security_event()
        except Exception:
            pass
        return False
    challenge.attempts += 1
    valid = hmac.compare_digest(challenge.code_hash, _hash_otp(code))
    if not valid:
        try:
            from metrics import record_security_event
            record_security_event()
        except Exception:
            pass
    if valid:
        challenge.consumed_at = now
    session.flush()
    return valid