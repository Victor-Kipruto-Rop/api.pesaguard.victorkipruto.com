"""Append-only storage for raw and processed transaction stage evidence."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Mapping

from models import TransformationRecord

STAGES = frozenset({"RAW", "VALIDATED", "NORMALIZED", "ENRICHED", "PROCESSED"})


def record_transformation_stage(
    session: Any,
    *,
    tenant_id: str,
    transaction_id: str,
    event_id: str,
    stage: str,
    payload: Mapping[str, Any],
    source_event_id: str = "",
) -> TransformationRecord:
    """Insert one immutable stage record, returning the existing record on replay."""
    normalized_stage = str(stage).upper()
    if normalized_stage not in STAGES:
        raise ValueError(f"unsupported transformation stage: {stage}")
    existing = session.query(TransformationRecord).filter_by(
        tenant_id=tenant_id,
        event_id=event_id,
        stage=normalized_stage,
    ).first()
    if existing is not None:
        return existing
    payload_dict = dict(payload)
    payload_hash = hashlib.sha256(
        json.dumps(payload_dict, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()
    record = TransformationRecord(
        id=f"stage_{uuid.uuid4().hex}",
        tenant_id=tenant_id,
        transaction_id=transaction_id,
        event_id=event_id,
        source_event_id=source_event_id or None,
        stage=normalized_stage,
        payload=payload_dict,
        payload_hash=payload_hash,
        created_at=datetime.now(timezone.utc),
    )
    session.add(record)
    return record