"""On-call rotation tracking and operator management service for PesaGuard."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from models import OnCallRotation

logger = logging.getLogger("pesaguard.on_call")


def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Ensure a datetime object is localized to UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _parse_iso_datetime(val: Any) -> Optional[datetime]:
    """Parse string or datetime input safely into a UTC datetime object."""
    if not val:
        return None
    if isinstance(val, datetime):
        return _ensure_utc(val)

    text = str(val).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"

    try:
        dt = datetime.fromisoformat(text)
        return _ensure_utc(dt)
    except ValueError as exc:
        logger.warning("Failed to parse ISO datetime string '%s': %s", val, exc)
        return None


class OnCallService:
    """Manages operator on-call schedules, shift coverage, and escalation chains."""

    def __init__(self, session: Session):
        self.session = session

    def create_rotation(
        self,
        tenant_id: str,
        operator_id: str,
        operator_name: str,
        operator_email: str,
        operator_phone: str,
        shift_start: datetime | str,
        shift_end: datetime | str,
        escalation_level: int = 1,
    ) -> Dict[str, Any]:
        """Create a new on-call operator shift rotation."""
        start_dt = _parse_iso_datetime(shift_start)
        end_dt = _parse_iso_datetime(shift_end)

        if not start_dt or not end_dt or start_dt >= end_dt:
            raise ValueError("Invalid shift schedule: shift_start must be prior to shift_end.")

        rotation_id = f"rotation_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)
        is_active = start_dt <= now < end_dt

        rotation = OnCallRotation(
            id=rotation_id,
            tenant_id=tenant_id or "default",
            operator_id=operator_id,
            operator_name=operator_name,
            operator_email=operator_email,
            operator_phone=operator_phone,
            shift_start=start_dt,
            shift_end=end_dt,
            is_active=is_active,
            escalation_level=escalation_level,
            created_at=now,
        )
        self.session.add(rotation)
        self.session.commit()
        logger.info("Created shift rotation_id=%s for operator_id=%s", rotation_id, operator_id)
        return self._rotation_to_dict(rotation)

    def get_active_rotations(
        self,
        tenant_id: str,
        escalation_level: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve currently active on-call operator shifts for a tenant."""
        now = datetime.now(timezone.utc)
        query = self.session.query(OnCallRotation).filter(
            OnCallRotation.tenant_id == tenant_id,
            OnCallRotation.shift_start <= now,
            OnCallRotation.shift_end > now,
        )
        if escalation_level is not None:
            query = query.filter(OnCallRotation.escalation_level == escalation_level)

        rotations = query.order_by(OnCallRotation.escalation_level.asc()).all()
        return [self._rotation_to_dict(r) for r in rotations]

    def get_upcoming_rotations(
        self,
        tenant_id: str,
        hours_ahead: int = 24,
    ) -> List[Dict[str, Any]]:
        """Retrieve scheduled future on-call shifts within a given window."""
        now = datetime.now(timezone.utc)
        future = now + timedelta(hours=hours_ahead)

        rotations = (
            self.session.query(OnCallRotation)
            .filter(
                OnCallRotation.tenant_id == tenant_id,
                OnCallRotation.shift_start > now,
                OnCallRotation.shift_start <= future,
            )
            .order_by(OnCallRotation.shift_start.asc())
            .all()
        )
        return [self._rotation_to_dict(r) for r in rotations]

    def get_rotation_history(
        self,
        tenant_id: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Fetch past on-call rotations for audit and history logs."""
        now = datetime.now(timezone.utc)
        rotations = (
            self.session.query(OnCallRotation)
            .filter(
                OnCallRotation.tenant_id == tenant_id,
                OnCallRotation.shift_end <= now,
            )
            .order_by(OnCallRotation.shift_end.desc())
            .limit(limit)
            .all()
        )
        return [self._rotation_to_dict(r) for r in rotations]

    def get_operator_schedule(
        self,
        tenant_id: str,
        operator_id: str,
        days_ahead: int = 30,
    ) -> List[Dict[str, Any]]:
        """Retrieve upcoming schedule for a specific operator."""
        now = datetime.now(timezone.utc)
        future = now + timedelta(days=days_ahead)

        rotations = (
            self.session.query(OnCallRotation)
            .filter(
                OnCallRotation.tenant_id == tenant_id,
                OnCallRotation.operator_id == operator_id,
                OnCallRotation.shift_start >= now,
                OnCallRotation.shift_start <= future,
            )
            .order_by(OnCallRotation.shift_start.asc())
            .all()
        )
        return [self._rotation_to_dict(r) for r in rotations]

    def update_rotation(self, rotation_id: str, **kwargs) -> Dict[str, Any]:
        """Update properties or shift times of an existing rotation."""
        rotation = self.session.query(OnCallRotation).filter(OnCallRotation.id == rotation_id).first()
        if not rotation:
            return {"error": "rotation_not_found"}

        now = datetime.now(timezone.utc)
        if "shift_start" in kwargs:
            kwargs["shift_start"] = _parse_iso_datetime(kwargs["shift_start"])
        if "shift_end" in kwargs:
            kwargs["shift_end"] = _parse_iso_datetime(kwargs["shift_end"])

        shift_start = kwargs.get("shift_start", rotation.shift_start)
        shift_end = kwargs.get("shift_end", rotation.shift_end)
        if shift_start and shift_end:
            kwargs["is_active"] = shift_start <= now < shift_end

        for key, value in kwargs.items():
            if hasattr(rotation, key):
                setattr(rotation, key, value)

        self.session.commit()
        logger.info("Updated rotation_id=%s", rotation_id)
        return self._rotation_to_dict(rotation)

    def delete_rotation(self, rotation_id: str) -> Dict[str, Any]:
        """Delete an on-call rotation record."""
        rotation = self.session.query(OnCallRotation).filter(OnCallRotation.id == rotation_id).first()
        if not rotation:
            return {"error": "rotation_not_found"}

        self.session.delete(rotation)
        self.session.commit()
        logger.info("Deleted rotation_id=%s", rotation_id)
        return {"status": "deleted", "id": rotation_id}

    def get_coverage_status(self, tenant_id: str) -> Dict[str, Any]:
        """Evaluate active and upcoming coverage across escalation tiers."""
        active_rotations = self.get_active_rotations(tenant_id)
        upcoming_rotations = self.get_upcoming_rotations(tenant_id, hours_ahead=4)

        coverage_by_level: Dict[int, List[Dict[str, Any]]] = {}
        for rotation in active_rotations:
            level = rotation["escalation_level"]
            coverage_by_level.setdefault(level, []).append(rotation)

        return {
            "tenant_id": tenant_id,
            "currently_covered": len(active_rotations) > 0,
            "active_operators": len(active_rotations),
            "coverage_by_level": coverage_by_level,
            "upcoming_shifts": len(upcoming_rotations),
            "next_shift": upcoming_rotations[0] if upcoming_rotations else None,
        }

    def bulk_create_rotations(
        self,
        tenant_id: str,
        rotations_data: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Bulk create shift schedules safely using nested database savepoints."""
        created = []
        errors = []

        for data in rotations_data:
            try:
                result = self.create_rotation(
                    tenant_id=tenant_id,
                    operator_id=data["operator_id"],
                    operator_name=data.get("operator_name", ""),
                    operator_email=data.get("operator_email", ""),
                    operator_phone=data.get("operator_phone", ""),
                    shift_start=data["shift_start"],
                    shift_end=data["shift_end"],
                    escalation_level=data.get("escalation_level", 1),
                )
                created.append(result)
            except Exception as exc:
                try:
                    self.session.rollback()
                except Exception:
                    pass
                logger.error("Failed creating bulk rotation entry: %s", exc)
                errors.append({"data": data, "error": str(exc)})

        return {
            "created": len(created),
            "errors": len(errors),
            "rotations": created,
            "failed": errors,
        }

    def notify_escalation(
        self,
        tenant_id: str,
        incident_id: str,
        severity: str,
        message: str,
        escalation_level: int = 1,
    ) -> Dict[str, Any]:
        """Identify active on-call operator and dispatch emergency alerts via SMS and Email."""
        try:
            from alerting import send_email_alert, send_sms_alert
        except ImportError:
            from alert_service import send_email_alert, send_sms_alert

        active_ops = self.get_active_rotations(tenant_id, escalation_level=escalation_level)
        if not active_ops:
            logger.warning(
                "No active on-call operator at level %d for tenant_id=%s",
                escalation_level, tenant_id
            )
            return {
                "status": "failed",
                "reason": "no_active_operator",
                "escalation_level": escalation_level,
            }

        operator = active_ops[0]
        operator_id = operator.get("operator_id")
        operator_name = operator.get("operator_name")
        operator_email = operator.get("operator_email")
        operator_phone = operator.get("operator_phone")

        discrepancy_payload = {
            "trans_id": incident_id,
            "severity": severity,
            "status": "escalated",
            "tenant_id": tenant_id,
            "anomalies": [message],
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

        notifications_sent = []

        if operator_phone:
            try:
                sms_ok = send_sms_alert(discrepancy_payload)
                notifications_sent.append({"channel": "sms", "status": "sent" if sms_ok else "failed"})
            except Exception as exc:
                logger.error("SMS dispatch exception for %s: %s", operator_phone, exc)
                notifications_sent.append({"channel": "sms", "status": "error", "error": str(exc)})

        if operator_email:
            try:
                email_ok = send_email_alert(discrepancy_payload)
                notifications_sent.append({"channel": "email", "status": "sent" if email_ok else "failed"})
            except Exception as exc:
                logger.error("Email dispatch exception for %s: %s", operator_email, exc)
                notifications_sent.append({"channel": "email", "status": "error", "error": str(exc)})

        logger.info(
            "Escalation notification dispatched to %s (level %d) for incident_id=%s",
            operator_name, escalation_level, incident_id
        )

        return {
            "status": "sent",
            "operator_id": operator_id,
            "operator_name": operator_name,
            "escalation_level": escalation_level,
            "notifications": notifications_sent,
        }

    def get_escalation_chain(
        self,
        tenant_id: str,
        start_level: int = 1,
        max_levels: int = 3,
    ) -> List[Dict[str, Any]]:
        """Construct escalation sequence chain across operator coverage levels."""
        chain = []
        for level in range(start_level, start_level + max_levels):
            active_ops = self.get_active_rotations(tenant_id, escalation_level=level)
            if active_ops:
                chain.extend(active_ops)
            else:
                break

        return chain

    def _rotation_to_dict(self, rotation: OnCallRotation) -> Dict[str, Any]:
        """Convert OnCallRotation ORM entity into a serialized dictionary."""
        start_iso = rotation.shift_start.isoformat() if rotation.shift_start else None
        end_iso = rotation.shift_end.isoformat() if rotation.shift_end else None
        created_iso = rotation.created_at.isoformat() if rotation.created_at else None

        return {
            "id": rotation.id,
            "tenant_id": rotation.tenant_id,
            "operator_id": rotation.operator_id,
            "operator_name": rotation.operator_name,
            "operator_email": rotation.operator_email,
            "operator_phone": rotation.operator_phone,
            "shift_start": start_iso,
            "shift_end": end_iso,
            "is_active": rotation.is_active,
            "escalation_level": rotation.escalation_level,
            "created_at": created_iso,
        }
