"""Append-only source-to-output lineage recording and tracing."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from models import LineageRecord


def record_lineage(
    session: Any,
    *,
    tenant_id: str,
    transaction_id: str,
    event_id: str,
    stage: str,
    source: str,
    source_event_id: str = "",
    upstream_event_id: str = "",
    pipeline_version: str = "1",
    transformation_version: str = "1",
    job_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    ingestion_time: Optional[datetime] = None,
) -> LineageRecord:
    existing = session.query(LineageRecord).filter_by(
        tenant_id=tenant_id,
        event_id=event_id,
        stage=stage,
    ).first()
    if existing is not None:
        return existing
    record = LineageRecord(
        id=f"lineage_{uuid.uuid4().hex}",
        tenant_id=tenant_id,
        transaction_id=transaction_id,
        event_id=event_id,
        stage=stage,
        source=source,
        source_event_id=source_event_id or None,
        upstream_event_id=upstream_event_id or None,
        ingestion_time=ingestion_time or datetime.now(timezone.utc),
        pipeline_version=pipeline_version,
        transformation_version=transformation_version,
        job_id=job_id,
        correlation_id=correlation_id,
    )
    session.add(record)
    return record


def trace_transaction(session: Any, *, tenant_id: str, transaction_id: str) -> list[LineageRecord]:
    """Return the tenant-scoped lineage chain in creation order."""
    return session.query(LineageRecord).filter(
        LineageRecord.tenant_id == tenant_id,
        LineageRecord.transaction_id == transaction_id,
    ).order_by(LineageRecord.created_at.asc(), LineageRecord.id.asc()).all()