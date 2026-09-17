"""Phase 9 schema evolution metadata.

Schema evolution is tracked so every decision can be traced back to the exact
schema and pipeline version that produced it, as required by the exit gate:

- Where did this data originate?
- Which version processed it?
- What was the final decision?

This module is intentionally conservative: it records versions and provides a
hook for compatibility checks, but it does not auto-migrate payloads unless the
processing path explicitly asks for it.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from data_lineage import SCHEMA_VERSION_KEY, PIPELINE_VERSION_KEY

_COMPATIBLE = "compatible"
_MIGRATION_REQUIRED = "migration_required"
_INCOMPATIBLE = "incompatible"


def schema_version_from_payload(payload: Dict[str, Any]) -> Optional[str]:
    """Extract the declared schema version from a payload, if present."""
    return _pick(payload, SCHEMA_VERSION_KEY, "SchemaVersion", "schema_version", "event_version")


def pipeline_version_from_context(context: Dict[str, Any]) -> Optional[str]:
    """Extract the pipeline version from processing context, if present."""
    return _pick(context, PIPELINE_VERSION_KEY, "pipeline_version")


def version_pair(schema_version: Optional[str], pipeline_version: Optional[str]) -> Dict[str, Optional[str]]:
    return {SCHEMA_VERSION_KEY: schema_version, PIPELINE_VERSION_KEY: pipeline_version}


def assess_schema_compatibility(current_version: str, incoming_version: str) -> Tuple[str, str]:
    """Assess whether an incoming schema version is compatible with the current one.

    Returns ``(compatibility, note)``.

    This is a conservative placeholder contract. Real deployments should extend
    it with explicit version-to-version migration rules.
    """
    if current_version == incoming_version:
        return _COMPATIBLE, "same version"
    if incoming_version in ("1.0", "1.1") and current_version.startswith("1."):
        return _MIGRATION_REQUIRED, "minor schema change may require normalization"
    return _INCOMPATIBLE, "unsupported schema version"


def _pick(source: Dict[str, Any], *keys: str) -> Optional[str]:
    for key in keys:
        if key in source:
            value = source[key]
            if isinstance(value, str):
                return value.strip() or None
            if isinstance(value, (int, float)):
                return str(value)
    return None
