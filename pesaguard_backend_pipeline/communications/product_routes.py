from __future__ import annotations

import csv
import io
import uuid
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request, Response

from .core.enums import CommunicationChannel
from .domain import approve_template, create_template, issue_otp, set_consent, verify_otp
from .models import CommunicationCampaign, CommunicationConsent, CommunicationNotification, CommunicationOtpChallenge, CommunicationPreference, CommunicationTemplate

# Mirrors CommunicationNotification.ck_communication_notification_status so the
# API rejects unknown filter/export values instead of leaking query behavior.
NOTIFICATION_STATUSES = frozenset({
    "created", "queued", "processing", "accepted", "submitted", "sent",
    "delivered", "opened", "clicked", "bounced", "complained", "failed",
    "rejected", "expired", "cancelled", "retrying", "dead_letter",
})


def create_product_blueprint(session_factory, require_auth_fn, current_user_fn):
    blueprint = Blueprint("communications_product", __name__, url_prefix="/api/v1/communications")

    def tenant_id():
        user = current_user_fn()
        return getattr(user, "tenant_id", None)

    @blueprint.get("/templates")
    @require_auth_fn("read:communications")
    def templates():
        session = session_factory()
        try:
            rows = session.query(CommunicationTemplate).filter_by(tenant_id=tenant_id()).order_by(CommunicationTemplate.slug, CommunicationTemplate.version.desc()).all()
            return jsonify([_template_payload(row) for row in rows])
        finally:
            session.close()

    @blueprint.post("/templates")
    @require_auth_fn("send:communications")
    def create_template_route():
        payload = request.get_json(silent=True) or {}
        try:
            channel = CommunicationChannel(str(payload["channel"]).lower())
            session = session_factory()
            template = create_template(session, tenant_id=tenant_id(), slug=str(payload["slug"]), channel=channel, body=str(payload["body"]), variables=list(payload.get("variables", [])))
            session.commit()
            return jsonify(_template_payload(template)), 201
        except (KeyError, ValueError, TypeError) as exc:
            return jsonify({"error": str(exc)}), 400
        finally:
            if "session" in locals():
                session.close()

    @blueprint.post("/templates/<template_id>/approve")
    @require_auth_fn("manage:communications")
    def approve_template_route(template_id):
        session = session_factory()
        try:
            template = session.query(CommunicationTemplate).filter_by(id=template_id, tenant_id=tenant_id()).one_or_none()
            if template is None:
                return jsonify({"error": "template_not_found"}), 404
            approve_template(session, template, str(getattr(current_user_fn(), "user_id", "system")))
            session.commit()
            return jsonify(_template_payload(template))
        finally:
            session.close()

    @blueprint.put("/preferences/<path:recipient>")
    @require_auth_fn("manage:communications")
    def preference_route(recipient):
        session = session_factory()
        try:
            payload = request.get_json(silent=True) or {}
            preference = session.query(CommunicationPreference).filter_by(tenant_id=tenant_id(), recipient=recipient).one_or_none()
            if preference is None:
                preference = CommunicationPreference(id=f"preference_{uuid.uuid4().hex}", tenant_id=tenant_id(), recipient=recipient)
                session.add(preference)
            for key in ("channels", "quiet_hours_start", "quiet_hours_end", "timezone", "marketing_opt_in"):
                if key in payload:
                    setattr(preference, key, payload[key])
            session.commit()
            return jsonify({"recipient": recipient, "channels": preference.channels, "quiet_hours_start": preference.quiet_hours_start, "quiet_hours_end": preference.quiet_hours_end, "timezone": preference.timezone, "marketing_opt_in": bool(preference.marketing_opt_in)})
        finally:
            session.close()

    @blueprint.put("/consent/<path:recipient>")
    @require_auth_fn("manage:communications")
    def consent_route(recipient):
        payload = request.get_json(silent=True) or {}
        try:
            session = session_factory()
            consent = set_consent(session, tenant_id=tenant_id(), recipient=recipient, channel=CommunicationChannel(str(payload["channel"]).lower()), purpose=str(payload.get("purpose", "transactional")), granted=bool(payload["granted"]), source=str(payload.get("source", "api")))
            session.commit()
            return jsonify({"id": consent.id, "granted": bool(consent.granted)})
        except (KeyError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 400
        finally:
            if "session" in locals():
                session.close()

    @blueprint.post("/otp")
    @require_auth_fn("send:communications")
    def issue_otp_route():
        payload = request.get_json(silent=True) or {}
        session = session_factory()
        try:
            challenge, code = issue_otp(session, tenant_id=tenant_id(), recipient=str(payload["recipient"]), purpose=str(payload.get("purpose", "login")))
            session.commit()
            return jsonify({"challenge_id": challenge.id, "expires_at": challenge.expires_at.isoformat(), "delivery_required": True}), 202
        except KeyError as exc:
            return jsonify({"error": str(exc)}), 400
        finally:
            session.close()

    @blueprint.post("/otp/<challenge_id>/verify")
    @require_auth_fn("send:communications")
    def verify_otp_route(challenge_id):
        session = session_factory()
        try:
            challenge = session.query(CommunicationOtpChallenge).filter_by(id=challenge_id, tenant_id=tenant_id()).one_or_none()
            if challenge is None:
                return jsonify({"verified": False}), 404
            valid = verify_otp(session, challenge, str((request.get_json(silent=True) or {}).get("code", "")))
            session.commit()
            return jsonify({"verified": valid}), 200 if valid else 401
        finally:
            session.close()

    @blueprint.post("/campaigns")
    @require_auth_fn("send:communications")
    def campaign_route():
        payload = request.get_json(silent=True) or {}
        session = session_factory()
        try:
            campaign = CommunicationCampaign(id=f"campaign_{uuid.uuid4().hex}", tenant_id=tenant_id(), name=str(payload["name"]), template_id=str(payload["template_id"]), channel=str(payload["channel"]).lower(), audience=payload.get("audience", []), scheduled_at=_parse_datetime(payload.get("scheduled_at")), status="scheduled" if payload.get("scheduled_at") else "queued")
            session.add(campaign)
            session.commit()
            return jsonify({"id": campaign.id, "status": campaign.status}), 202
        except (KeyError, ValueError) as exc:
            session.rollback()
            return jsonify({"error": str(exc)}), 400
        finally:
            session.close()

    @blueprint.get("/analytics")
    @require_auth_fn("read:communications")
    def analytics_route():
        session = session_factory()
        try:
            rows = session.query(CommunicationNotification.status, CommunicationNotification.channel).filter_by(tenant_id=tenant_id()).all()
            by_status, by_channel = {}, {}
            for status, channel in rows:
                by_status[status] = by_status.get(status, 0) + 1
                by_channel[channel] = by_channel.get(channel, 0) + 1
            return jsonify({"total": len(rows), "by_status": by_status, "by_channel": by_channel})
        finally:
            session.close()

    @blueprint.get("/search")
    @require_auth_fn("read:communications")
    def search_route():
        requested_status = (request.args.get("status") or "").strip()
        if requested_status and requested_status not in NOTIFICATION_STATUSES:
            return jsonify({"error": "unknown_status"}), 400
        raw_query = (request.args.get("q") or "").strip()
        if len(raw_query) > 255:
            return jsonify({"error": "query_too_long"}), 400
        session = session_factory()
        try:
            query = session.query(CommunicationNotification).filter_by(tenant_id=tenant_id())
            if requested_status:
                query = query.filter_by(status=requested_status)
            if raw_query:
                query = query.filter(CommunicationNotification.recipient.contains(raw_query))
            rows = query.order_by(CommunicationNotification.created_at.desc()).limit(500).all()
            return jsonify([{"id": row.id, "channel": row.channel, "recipient": row.recipient, "status": row.status, "created_at": row.created_at.isoformat()} for row in rows])
        finally:
            session.close()

    @blueprint.get("/export")
    @require_auth_fn("export:communications")
    def export_route():
        session = session_factory()
        try:
            rows = session.query(CommunicationNotification).filter_by(tenant_id=tenant_id()).order_by(CommunicationNotification.created_at.desc()).limit(5000).all()
            stream = io.StringIO()
            writer = csv.writer(stream)
            writer.writerow(["id", "channel", "recipient", "status", "created_at"])
            for row in rows:
                writer.writerow([_csv_cell(row.id), _csv_cell(row.channel), _csv_cell(row.recipient), _csv_cell(row.status), _csv_cell(row.created_at.isoformat())])
            return Response(stream.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=communications.csv"})
        finally:
            session.close()

    return blueprint


def _template_payload(template):
    return {"id": template.id, "slug": template.slug, "version": template.version, "channel": template.channel, "body": template.body, "variables": template.variables, "status": template.status, "approved_by": template.approved_by}


def _parse_datetime(value):
    if not value:
        return None
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _csv_cell(value):
    text = "" if value is None else str(value)
    return f"'{text}" if text.lstrip(" \t\r\n")[:1] in {"=", "+", "-", "@"} else text