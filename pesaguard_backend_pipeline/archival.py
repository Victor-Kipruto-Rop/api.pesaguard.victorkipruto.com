"""Policy-driven hot, warm, and cold transaction archival."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Optional


class ArchivalPolicyError(ValueError):
    """Raised when archival windows are missing or inconsistent."""


@dataclass(frozen=True)
class RetentionPolicy:
    """Business-approved windows, expressed in days from transaction time."""

    hot_days: int
    warm_days: int
    cold_days: int

    def __post_init__(self) -> None:
        if not 0 < self.hot_days < self.warm_days < self.cold_days:
            raise ArchivalPolicyError("retention windows must satisfy 0 < hot_days < warm_days < cold_days")


@dataclass(frozen=True)
class ArchiveManifest:
    tenant_id: str
    transaction_id: str
    tier: str
    object_key: str
    payload_hash: str
    archived_at: str


class ArchiveObjectStore:
    """Local object-store implementation with a replaceable S3-compatible boundary."""

    def __init__(self, root: Optional[str] = None):
        self.root = Path(root or "var/archive")

    def put(self, key: str, content: bytes) -> None:
        destination = self.root / key
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)

    def get(self, key: str) -> bytes:
        return (self.root / key).read_bytes()


class ArchiveManager:
    def __init__(self, policy: RetentionPolicy, store: Optional[ArchiveObjectStore] = None):
        self.policy = policy
        self.store = store or ArchiveObjectStore()

    def tier_for(self, occurred_at: datetime, *, now: Optional[datetime] = None) -> str:
        current = now or datetime.now(timezone.utc)
        timestamp = occurred_at.astimezone(timezone.utc) if occurred_at.tzinfo else occurred_at.replace(tzinfo=timezone.utc)
        age = current - timestamp
        if age < timedelta(days=self.policy.hot_days):
            return "hot"
        if age < timedelta(days=self.policy.warm_days):
            return "warm"
        if age < timedelta(days=self.policy.cold_days):
            return "cold"
        return "expired"

    def archive(self, transaction: Mapping[str, Any], *, now: Optional[datetime] = None) -> Optional[ArchiveManifest]:
        tenant_id = str(transaction.get("tenant_id") or "").strip()
        transaction_id = str(transaction.get("transaction_id") or transaction.get("TransID") or "").strip()
        if not tenant_id or not transaction_id:
            raise ArchivalPolicyError("tenant_id and transaction_id are required for archival")
        occurred_at = datetime.fromisoformat(str(transaction.get("transaction_time") or transaction.get("TransTime")).replace("Z", "+00:00"))
        tier = self.tier_for(occurred_at, now=now)
        if tier in {"hot", "expired"}:
            return None
        payload = json.dumps(dict(transaction), sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        payload_hash = hashlib.sha256(payload).hexdigest()
        timestamp = occurred_at.astimezone(timezone.utc)
        key = f"tier={tier}/tenant={tenant_id}/year={timestamp.year:04d}/month={timestamp.month:02d}/day={timestamp.day:02d}/{transaction_id}.json"
        self.store.put(key, payload)
        return ArchiveManifest(tenant_id, transaction_id, tier, key, payload_hash, (now or datetime.now(timezone.utc)).isoformat())