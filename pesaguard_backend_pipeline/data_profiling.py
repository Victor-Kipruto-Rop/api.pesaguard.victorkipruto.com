"""Phase 9 data profiling.

Profiles describe the shape and trust characteristics of a payload without
changing it. They are used for lineage annotations, DQ context, and schema
evolution decisions.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from data_lineage import SCHEMA_VERSION_KEY, PIPELINE_VERSION_KEY


def profile_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Return a read-only profile of the payload shape and basic completeness."""
    if not isinstance(payload, dict):
        return {"type": "non_object", "keys": [], "sample_size": 0}

    keys = list(payload.keys())
    non_empty = [k for k in keys if payload[k] not in (None, "", [], {})]
    sample_size = sum(_sample_len(payload.get(k)) for k in keys)

    return {
        "type": "object",
        "key_count": len(keys),
        "non_empty_key_count": len(non_empty),
        "keys": keys,
        "sample_size": sample_size,
    }


def profile_record(record: Dict[str, Any], required_keys: Optional[List[str]] = None) -> Dict[str, Any]:
    """Profile a single transaction-like record against an optional required-key list."""
    base = profile_payload(record)
    base["required_keys"] = required_keys or []
    base["missing_required_keys"] = [k for k in (required_keys or []) if k not in record or record[k] in (None, "", [])]
    return base


def _sample_len(value: Any) -> int:
    if isinstance(value, str):
        return len(value)
    if isinstance(value, (list, tuple, set)):
        return len(value)
    if isinstance(value, dict):
        return len(value)
    return 1
