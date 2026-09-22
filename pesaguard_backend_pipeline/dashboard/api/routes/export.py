"""
Dashboard CSV Export REST API Blueprint for PesaGuard.

Provides secure, tenant-scoped streaming CSV exports for transaction discrepancies,
audit records, and reconciliation audit trails with RBAC enforcement.
"""

from __future__ import annotations

import csv
import io
import logging
import re
from datetime import datetime, timezone
from typing import Any, Generator, Optional

from flask import Blueprint, Response, g, jsonify, request, stream_with_context

from pesaguard_backend_pipeline.rbac import PERM_VIEW_DISCREPANCIES, has_permission
from pesaguard_backend_pipeline.models import Discrepancy
from pesaguard_backend_pipeline.app_2 import SessionLocal

logger = logging.getLogger("pesaguard.dashboard_export")

bp = Blueprint("dashboard_export", __name__, url_prefix="/v1")
MAX_EXPORT_ROWS = 5000


def _sanitize_csv_cell(value: Any) -> str:
    """Sanitize cell values to prevent CSV formula injection (CSV Injection / DDE)."""
    if value is None:
        return ""
    val_str = str(value)
    # Check past leading whitespace because spreadsheet applications may trim it.
    first_content = val_str.lstrip(" \t\r\n")[:1]
    return f"'{val_str}" if first_content in {"=", "+", "-", "@"} else val_str


def _parse_iso_datetime(date_str: Optional[str]) -> Optional[datetime]:
    """Parse ISO date string into a timezone-aware UTC datetime object."""
    if not date_str:
        return None
    try:
        # Handle 'YYYY-MM-DD' or full ISO format
        cleaned = date_str.strip()
        if len(cleaned) == 10:
            cleaned += "T00:00:00Z"
        dt = datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


@bp.route("/export/csv", methods=["GET"])
def export_csv():
    """Stream CSV export of discrepancy records for an authorized tenant."""
    # 1. Extract context & authorization
    user = getattr(g, "user", None)
    if user is None:
        return jsonify({"error": "unauthorized", "message": "Authentication is required."}), 401

    permissions = set(getattr(user, "permissions", ()) or ())
    roles = getattr(user, "roles", ()) or ()
    role = getattr(user, "role", None) or (roles[0] if roles else None)
    has_export_permission = (
        PERM_VIEW_DISCREPANCIES in permissions
        or "*" in permissions
        or "manage:*" in permissions
        or any(has_permission(candidate, PERM_VIEW_DISCREPANCIES) for candidate in roles)
        or (role is not None and has_permission(role, PERM_VIEW_DISCREPANCIES))
    )

    if not has_export_permission:
        return jsonify({"error": "forbidden", "message": "Insufficient permissions to export discrepancy records."}), 403

    tenant_id = (
        (request.args.get("tenant_id") or "").strip()
        or str(getattr(g, "tenant_id", None) or request.headers.get("X-Tenant-ID", "")).strip()
    )
    if not tenant_id:
        return jsonify({"error": "bad_request", "message": "tenant_id parameter is required."}), 400

    user_tenant_id = getattr(user, "tenant_id", None)
    can_access_all_tenants = "manage:all_tenants" in permissions
    if tenant_id != user_tenant_id and not can_access_all_tenants:
        return jsonify({"error": "forbidden", "message": "Access to this tenant is not permitted."}), 403

    # 2. Parse date filters
    from_value = request.args.get("from")
    to_value = request.args.get("to")
    dt_from = _parse_iso_datetime(from_value)
    dt_to = _parse_iso_datetime(to_value)
    if from_value and dt_from is None:
        return jsonify({"error": "bad_request", "message": "Invalid 'from' ISO date format."}), 400
    if to_value and dt_to is None:
        return jsonify({"error": "bad_request", "message": "Invalid 'to' ISO date format."}), 400
    if dt_from and dt_to and dt_from > dt_to:
        return jsonify({"error": "bad_request", "message": "'from' must be earlier than or equal to 'to'."}), 400

    safe_tenant_id = re.sub(r"[^A-Za-z0-9_.-]", "_", tenant_id)[:64] or "tenant"
    filename = f"pesaguard-discrepancies-{safe_tenant_id}-{datetime.now(timezone.utc).strftime('%Y%m%d')}.csv"

    @stream_with_context
    def generate_csv_stream() -> Generator[str, None, None]:
        """Stream rows while retaining the database session for the full iteration."""
        session = SessionLocal()
        try:
            query = session.query(Discrepancy).filter(Discrepancy.tenant_id == tenant_id)
            if dt_from:
                query = query.filter(Discrepancy.detected_at >= dt_from)
            if dt_to:
                query = query.filter(Discrepancy.detected_at <= dt_to)

            query = query.order_by(
                Discrepancy.detected_at.desc(),
                Discrepancy.id.desc(),
            ).limit(MAX_EXPORT_ROWS)

            stream_output = io.StringIO(newline="")
            fieldnames = ["id", "trans_id", "anomaly_type", "status", "severity", "resolved", "tenant_id", "detected_at"]
            writer = csv.DictWriter(stream_output, fieldnames=fieldnames)
            writer.writeheader()
            yield stream_output.getvalue()
            stream_output.seek(0)
            stream_output.truncate(0)

            for item in query.yield_per(500):
                detected_at = getattr(item, "detected_at", None)
                writer.writerow({
                    "id": _sanitize_csv_cell(getattr(item, "id", "")),
                    "trans_id": _sanitize_csv_cell(getattr(item, "trans_id", "")),
                    "anomaly_type": _sanitize_csv_cell(getattr(item, "anomaly_type", "")),
                    "status": _sanitize_csv_cell(getattr(item, "status", "")),
                    "severity": _sanitize_csv_cell(getattr(item, "severity", "")),
                    "resolved": "true" if getattr(item, "resolved", False) else "false",
                    "tenant_id": _sanitize_csv_cell(getattr(item, "tenant_id", "")),
                    "detected_at": _sanitize_csv_cell(detected_at.isoformat() if detected_at else ""),
                })
                yield stream_output.getvalue()
                stream_output.seek(0)
                stream_output.truncate(0)
        except Exception:
            logger.exception("CSV export failed during streaming for tenant_id=%s", tenant_id)
            raise
        finally:
            session.close()

    logger.info("Streaming CSV export for tenant_id=%s by role=%s", tenant_id, role)
    return Response(
        generate_csv_stream(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
