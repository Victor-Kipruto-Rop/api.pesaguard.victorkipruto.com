"""Workload-driven partition keys for raw objects, events, and query windows."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping


def _utc(value: Any = None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def raw_object_partition(tenant_id: str, source: str, observed_at: Any = None) -> str:
    """Return Hive-style object storage partitions for time-bounded raw files."""
    timestamp = _utc(observed_at)
    return "/".join((
        f"tenant={tenant_id}",
        f"source={str(source).strip().lower()}",
        f"year={timestamp.year:04d}",
        f"month={timestamp.month:02d}",
        f"day={timestamp.day:02d}",
    ))


def event_partition_key(event: Mapping[str, Any]) -> str:
    """Keep related events ordered by tenant, provider, and aggregate domain."""
    tenant = str(event.get("tenant_id") or "unknown")
    payload = event.get("payload") if isinstance(event.get("payload"), Mapping) else {}
    provider = str(event.get("source") or payload.get("provider") or "unknown").lower()
    aggregate = str(event.get("aggregate_id") or payload.get("transaction_id") or "unknown")
    return f"{tenant}:{provider}:{aggregate}"


def transaction_query_dimensions(*, tenant_id: str, start: datetime, end: datetime, provider: str | None = None) -> dict[str, Any]:
    """Declare the dimensions used by bounded operational transaction queries."""
    dimensions: dict[str, Any] = {"tenant_id": tenant_id, "created_at_start": _utc(start), "created_at_end": _utc(end)}
    if provider:
        dimensions["provider"] = provider.lower()
    return dimensions