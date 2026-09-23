"""Versioned external-source contract loading and validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator

from contract_versioning import validate_contract_version


class SourceContractError(ValueError):
    """Raised when an external source payload violates its provider contract."""


_SCHEMA_FILES = {
    "mpesa": "mpesa-1.0.json",
    "airtel-money": "airtel-money-1.0.json",
    "bank": "bank-1.0.json",
    "pos": "pos-merchant-1.0.json",
}
_SCHEMA_CACHE: dict[str, Mapping[str, Any]] = {}


def _schema_for(provider: str) -> Mapping[str, Any] | None:
    filename = _SCHEMA_FILES.get(provider)
    if filename is None:
        return None
    if provider not in _SCHEMA_CACHE:
        path = Path(__file__).with_name("schemas") / filename
        _SCHEMA_CACHE[provider] = json.loads(path.read_text(encoding="utf-8"))
    return _SCHEMA_CACHE[provider]


def validate_source_payload(provider: str, payload: Mapping[str, Any]) -> None:
    """Validate one provider payload before adapter normalization or persistence."""
    normalized_provider = str(provider).strip().lower()
    schema = _schema_for(normalized_provider)
    if schema is None:
        return
    if not isinstance(payload, Mapping):
        raise SourceContractError(f"{normalized_provider} payload must be an object")
    try:
        version = validate_contract_version(normalized_provider, str(payload.get("schema_version", "1.0")))
    except ValueError as exc:
        raise SourceContractError(str(exc)) from exc
    if version != "1.0":
        raise SourceContractError(f"{normalized_provider} schema {version} is not available")
    errors = sorted(Draft202012Validator(schema).iter_errors(dict(payload)), key=lambda error: list(error.path))
    if errors:
        error = errors[0]
        location = ".".join(str(part) for part in error.path) or "$"
        raise SourceContractError(f"{normalized_provider} schema 1.0 failed at {location}: {error.message}")