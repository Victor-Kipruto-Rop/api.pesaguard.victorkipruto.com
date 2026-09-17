"""Data access layer for Discrepancy records in PesaGuard.

Used by reconciliation_engine.py and reconciliation_job.py as part of an
atomic transaction alongside the idempotency ledger write — see both files'
_persist_atomically / reconcile_with_idempotency functions.

CRITICAL: Functions here NEVER call session.commit() or session.rollback()
themselves. The caller owns the transaction boundary — existing callers commit
once after this DAO's write succeeds alongside the idempotency ledger write,
ensuring both succeed or fail together. If this DAO committed on its own, it
would silently break that atomicity guarantee.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, List

from sqlalchemy.orm import Session, attributes

from models import Discrepancy

logger = logging.getLogger("pesaguard.discrepancy_dao")


def _serialize_details(details: Any) -> str:
    """Discrepancy.details is a Text column, so non-string payloads are serialized to JSON.

    Uses default=str as a safety net for non-primitive types (e.g., datetime objects).
    """
    if details is None:
        return ""
    if isinstance(details, str):
        return details
    try:
        return json.dumps(details, default=str)
    except (TypeError, ValueError) as exc:
        logger.warning("Failed to JSON-serialize discrepancy details: %s. Falling back to str().", exc)
        return str(details)


class DiscrepancyDAO:
    """Session-participating DAO — every method operates on the caller's session
    and never issues commit() or rollback()."""

    def save_discrepancy(
        self,
        session: Session,
        id: str,
        trans_id: str,
        tenant_id: Optional[str],
        anomaly_type: str,
        severity: str,
        details: Any,
        status: Optional[str] = None,
        assignee: Optional[str] = None,
    ) -> Discrepancy:
        """Create or update a Discrepancy record on the given session.

        id is expected to be deterministic per (trans_id, status) — e.g.
        f"{trans_id}-{status}" — so re-flagging the same transaction/status
        combination UPDATES the existing row instead of failing on duplicate PK.

        Does not commit or roll back. The caller owns transaction boundaries.
        """
        if not id or not trans_id:
            raise ValueError("Both 'id' and 'trans_id' must be provided to save_discrepancy.")

        scoped_id = f"{tenant_id or 'default'}:{id}"
        existing = (
            session.query(Discrepancy)
            .filter(Discrepancy.id == scoped_id, Discrepancy.tenant_id == (tenant_id or "default"))
            .first()
        )
        serialized_details = _serialize_details(details)

        if existing is not None:
            existing.anomaly_type = anomaly_type
            existing.severity = severity
            existing.details = serialized_details
            if status is not None:
                existing.status = status
            if tenant_id is not None:
                existing.tenant_id = tenant_id
            if assignee is not None:
                existing.assignee = assignee

            self._append_timeline(session, existing, event="updated", message=f"Re-flagged as {anomaly_type}")
            return existing

        now = datetime.now(timezone.utc)
        record = Discrepancy(
            id=scoped_id,
            trans_id=trans_id,
            tenant_id=tenant_id or "default",
            anomaly_type=anomaly_type,
            status=status or anomaly_type or "needs_review",
            severity=severity,
            details=serialized_details,
            resolved=False,
            detected_at=now,
            assignee=assignee,
            timeline=[{
                "ts": now.isoformat(),
                "event": "created",
                "message": f"Flagged as {anomaly_type}",
            }],
        )
        session.add(record)
        return record

    @staticmethod
    def _append_timeline(session: Session, record: Discrepancy, event: str, message: str) -> None:
        """Safely append timeline events while ensuring SQLAlchemy tracks JSON field mutations."""
        timeline: List[Dict[str, Any]] = list(record.timeline or [])
        timeline.append({
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "message": message,
        })
        record.timeline = timeline
        # Explicitly flag modification on JSON columns to guarantee ORM change tracking
        attributes.flag_modified(record, "timeline")

    def get_by_id(self, session: Session, id: str, tenant_id: Optional[str] = None) -> Optional[Discrepancy]:
        """Tenant-scoped fetch — enforces isolation when tenant_id is supplied."""
        if not id:
            return None

        record = session.get(Discrepancy, id)
        if record is None:
            return None
        if tenant_id is not None and getattr(record, "tenant_id", None) != tenant_id:
            from metrics import record_security_event
            record_security_event()
            logger.warning("Tenant isolation violation: record %s belongs to tenant %s, not %s", id, getattr(record, "tenant_id", None), tenant_id)
            return None
        return record


# Default singleton instance
discrepancy_dao = DiscrepancyDAO()
