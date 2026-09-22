"""Bulk campaign orchestration with safety gates and persisted control state.

Campaigns expand in bounded batches so a million-recipient campaign never
needs to fit in memory, recipients are streamed from durable per-recipient
rows, and pause/resume/cancel state survives worker restarts.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from sqlalchemy.orm import Session

from .application.notification_service import NotificationService
from .core.enums import CommunicationChannel
from .core.interfaces import NotificationRequest
from .cost import build_cost
from .domain import render_template
from .models import CommunicationCampaign, CommunicationCampaignRecipient, CommunicationTemplate


class CampaignStateError(ValueError):
    pass


_START_ALLOWED = {"draft", "queued", "scheduled"}
_PAUSE_ALLOWED = {"queued", "scheduled", "running"}
_RESUME_ALLOWED = {"paused"}
_CANCEL_ALLOWED = {"draft", "queued", "scheduled", "running", "paused"}


def _env_int(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, str(default))))
    except ValueError:
        return default


def _currency() -> str:
    return os.getenv("PESAGUARD_COMMUNICATION_CURRENCY", "KES")


def estimate_campaign(session: Session, campaign: CommunicationCampaign) -> dict[str, Any]:
    """Pre-flight safety estimate shown before a campaign may be confirmed."""
    template = session.query(CommunicationTemplate).filter_by(id=campaign.template_id, tenant_id=campaign.tenant_id).one_or_none()
    channel = CommunicationChannel(campaign.channel)
    recipients = 0
    segments = 0
    if template is not None:
        for item in campaign.audience or []:
            recipients += 1
            variables = item if isinstance(item, dict) else {}
            try:
                message = render_template(template, variables)
            except (KeyError, ValueError, IndexError):
                continue
            segments += build_cost(channel, message)["segments"]
    unit_cost = build_cost(channel, "x" * 160)["unit_cost"]
    estimated_cost = round(unit_cost * segments, 2)
    if recipients >= 100_000 or estimated_cost >= 100_000:
        risk = "HIGH"
    elif recipients >= 10_000 or estimated_cost >= 10_000:
        risk = "MEDIUM"
    else:
        risk = "LOW"
    return {
        "campaign_id": campaign.id,
        "recipients": recipients,
        "estimated_segments": segments,
        "estimated_cost": estimated_cost,
        "currency": _currency(),
        "risk": risk,
        "requires_explicit_confirmation": risk in {"MEDIUM", "HIGH"},
    }


def pause_campaign(session: Session, campaign: CommunicationCampaign) -> CommunicationCampaign:
    if campaign.status not in _PAUSE_ALLOWED:
        raise CampaignStateError(f"campaign cannot be paused from status {campaign.status!r}")
    campaign.status = "paused"
    campaign.paused_at = datetime.now(timezone.utc)
    session.flush()
    return campaign


def resume_campaign(session: Session, campaign: CommunicationCampaign) -> CommunicationCampaign:
    if campaign.status not in _RESUME_ALLOWED:
        raise CampaignStateError(f"campaign cannot be resumed from status {campaign.status!r}")
    campaign.status = "running"
    campaign.paused_at = None
    session.flush()
    return campaign


def cancel_campaign(session: Session, campaign: CommunicationCampaign) -> CommunicationCampaign:
    if campaign.status not in _CANCEL_ALLOWED:
        raise CampaignStateError(f"campaign cannot be cancelled from status {campaign.status!r}")
    campaign.status = "cancelled"
    campaign.completed_at = datetime.now(timezone.utc)
    session.query(CommunicationCampaignRecipient).filter(
        CommunicationCampaignRecipient.campaign_id == campaign.id,
        CommunicationCampaignRecipient.status == "pending",
    ).update({"status": "cancelled"}, synchronize_session=False)
    session.flush()
    return campaign


def campaign_progress(session: Session, campaign: CommunicationCampaign) -> dict[str, int]:
    rows = (
        session.query(CommunicationCampaignRecipient.status, func_count())
        .filter(CommunicationCampaignRecipient.campaign_id == campaign.id)
        .group_by(CommunicationCampaignRecipient.status)
        .all()
    )
    counts = {status: count for status, count in rows}
    return {
        "hydrated": sum(counts.values()),
        "pending": counts.get("pending", 0),
        "queued": counts.get("queued", 0),
        "failed": counts.get("failed", 0),
        "cancelled": counts.get("cancelled", 0),
    }


def func_count():
    from sqlalchemy import func

    return func.count("*")


def _hydrate_batch(session: Session, campaign: CommunicationCampaign, offset: int, batch_size: int) -> int:
    """Materialize the next slice of the audience as durable pending rows."""
    audience = campaign.audience or []
    hydrated = 0
    for item in audience[offset:offset + batch_size]:
        recipient = str(item.get("recipient") if isinstance(item, dict) else item)
        if not recipient:
            continue
        exists = session.query(CommunicationCampaignRecipient.id).filter_by(campaign_id=campaign.id, recipient=recipient).one_or_none()
        if exists is not None:
            continue
        session.add(CommunicationCampaignRecipient(
            id=f"campaign_recipient_{uuid.uuid4().hex}",
            campaign_id=campaign.id,
            recipient=recipient,
        ))
        hydrated += 1
    session.flush()
    return hydrated


def enqueue_due_campaign(
    session: Session,
    campaign: CommunicationCampaign,
    service: NotificationService,
    *,
    batch_size: int | None = None,
    rate_limiter: Callable[[], float] | None = None,
    now: datetime | None = None,
) -> int:
    """Expand a due campaign into idempotent notifications in bounded batches.

    Each invocation processes at most `batch_size` recipients, keeping memory
    flat for million-recipient audiences. Progress lives in the
    `communication_campaign_recipients` table, so pause/resume and worker
    restarts resume exactly where processing stopped.
    """
    now = now or datetime.now(timezone.utc)
    batch_size = batch_size or _env_int("PESAGUARD_CAMPAIGN_BATCH_SIZE", 5000)

    if campaign.status not in {"queued", "scheduled", "running"}:
        return 0
    scheduled_at = campaign.scheduled_at
    if scheduled_at is not None:
        if scheduled_at.tzinfo is None:
            scheduled_at = scheduled_at.replace(tzinfo=timezone.utc)
        if scheduled_at > now:
            return 0

    template = session.query(CommunicationTemplate).filter_by(
        id=campaign.template_id, tenant_id=campaign.tenant_id, status="approved"
    ).one_or_none()
    if template is None:
        campaign.status = "queued"
        campaign.last_error = "campaign template is missing or not approved"
        session.flush()
        return 0

    processed = 0
    campaign.status = "running"
    if campaign.started_at is None:
        campaign.started_at = now

    progress = campaign_progress(session, campaign)
    audience_size = len(campaign.audience or [])

    # Top up durable recipient rows before sending from them.
    if progress["hydrated"] < audience_size:
        _hydrate_batch(session, campaign, progress["hydrated"], batch_size)

    pending_rows = (
        session.query(CommunicationCampaignRecipient)
        .filter(CommunicationCampaignRecipient.campaign_id == campaign.id, CommunicationCampaignRecipient.status == "pending")
        .order_by(CommunicationCampaignRecipient.id.asc())
        .limit(batch_size)
        .all()
    )
    failures = 0
    for row in pending_rows:
        if rate_limiter is not None:
            wait = rate_limiter()
            if wait > 0:
                break  # respect the campaign rate limit; resume on next tick
        variables = {}
        for item in campaign.audience or []:
            candidate = str(item.get("recipient") if isinstance(item, dict) else item)
            if candidate == row.recipient:
                variables = item if isinstance(item, dict) else {}
                break
        try:
            message = render_template(template, variables)
            notification = service.enqueue(NotificationRequest(
                tenant_id=campaign.tenant_id,
                recipient=row.recipient,
                message=message,
                channel=CommunicationChannel(campaign.channel),
                idempotency_key=f"{campaign.id}:{row.recipient}",
                template_id=template.id,
                variables={**variables, "purpose": "marketing", "campaign_id": campaign.id},
            ))
            row.notification_id = notification.id
            row.status = "queued"
        except Exception as exc:
            row.status, row.error = "failed", str(exc)[:2000]
            failures += 1
        processed += 1

    campaign.processed_count = (campaign.processed_count or 0) + processed - failures
    campaign.failed_count = (campaign.failed_count or 0) + failures

    progress = campaign_progress(session, campaign)
    total_audience = audience_size
    done = progress["queued"] + progress["failed"] + progress["cancelled"]
    if total_audience and done >= total_audience and progress["pending"] == 0:
        campaign.status = "completed"
        campaign.completed_at = datetime.now(timezone.utc)
    elif processed == 0:
        # Nothing processed (rate limited or nothing hydrated yet): stay running.
        pass
    session.flush()
    return processed