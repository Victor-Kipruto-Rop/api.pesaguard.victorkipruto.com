from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional

LINEAGE_STAGES = [
    "provider",
    "webhook",
    "raw_event",
    "normalized",
    "fraud",
    "reconciliation",
    "exception",
    "report",
]


@dataclass(frozen=True)
class LineageEntry:
    """One immutable step in the data lifecycle for a single transaction."""

    stage: str
    service: str
    action: str
    schema_version: Optional[str] = None
    occurred_at: str = field(default_factory=lambda: _iso_now())
    metadata: Optional[Dict[str, object]] = None

    def to_dict(self) -> Dict[str, object]:
        payload: Dict[str, object] = {
            "stage": self.stage,
            "service": self.service,
            "action": self.action,
            "occurred_at": self.occurred_at,
        }
        if self.schema_version:
            payload["schema_version"] = self.schema_version
        if self.metadata:
            payload["metadata"] = self.metadata
        return payload


@dataclass(frozen=True)
class DataLineage:
    """Provable lineage chain for one business event.

    This is the contract behind the Phase 9 exit gate:

    - Where did this data originate?
    - What changed it?
    - Which service processed it?
    - Which version processed it?
    - What was the final decision?
    """

    lineage_id: str
    tenant_id: str
    event_id: str
    transaction_id: str
    provider_id: str
    entries: List[LineageEntry] = field(default_factory=list)
    final_decision: Optional[str] = None

    def add(self, entry: LineageEntry) -> DataLineage:
        """Return a new lineage with an appended stage entry (immutable)."""
        return DataLineage(
            lineage_id=self.lineage_id,
            tenant_id=self.tenant_id,
            event_id=self.event_id,
            transaction_id=self.transaction_id,
            provider_id=self.provider_id,
            entries=[*self.entries, entry],
            final_decision=self.final_decision,
        )

    def finalize(self, final_decision: str) -> DataLineage:
        return DataLineage(
            lineage_id=self.lineage_id,
            tenant_id=self.tenant_id,
            event_id=self.event_id,
            transaction_id=self.transaction_id,
            provider_id=self.provider_id,
            entries=list(self.entries),
            final_decision=final_decision,
        )

    def to_dict(self) -> Dict[str, object]:
        return {
            "lineage_id": self.lineage_id,
            "tenant_id": self.tenant_id,
            "event_id": self.event_id,
            "transaction_id": self.transaction_id,
            "provider_id": self.provider_id,
            "final_decision": self.final_decision,
            "stages": [entry.to_dict() for entry in self.entries],
        }

    def snapshot(self, stage: str, service: str, action: str, schema_version: Optional[str] = None, metadata: Optional[Dict[str, object]] = None) -> DataLineage:
        entry = LineageEntry(stage=stage, service=service, action=action, schema_version=schema_version, metadata=metadata)
        return self.add(entry)

    def has_stage(self, stage: str) -> bool:
        return any(entry.stage == stage for entry in self.entries)


def new_lineage_id() -> str:
    return "lineage_" + hashlib.sha256(json.dumps(_lineage_seed(), sort_keys=True).encode("utf-8")).hexdigest()[:32]


def _lineage_seed() -> Dict[str, str]:
    import uuid

    return {
        "lineage_id": uuid.uuid4().hex,
        "ts": datetime.now(timezone.utc).isoformat(),
    }


def build_lineage(event_id: str, transaction_id: str, tenant_id: str, provider_id: str, lineage_id: Optional[str] = None) -> DataLineage:
    return DataLineage(
        lineage_id=lineage_id or new_lineage_id(),
        tenant_id=tenant_id,
        event_id=event_id,
        transaction_id=transaction_id,
        provider_id=provider_id,
    )


SCHEMA_VERSION_KEY = "schema_version"
PIPELINE_VERSION_KEY = "pipeline_version"


def lineage_schema_version(lineage: DataLineage) -> Optional[str]:
    """Return the schema version attached to the earliest entry, if any."""
    if not lineage.entries:
        return None
    for entry in lineage.entries:
        if entry.schema_version:
            return entry.schema_version
    return None
