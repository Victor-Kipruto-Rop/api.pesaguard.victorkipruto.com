"""JSON Schema contracts for canonical transactions and versioned events."""

from __future__ import annotations

from typing import Any, Mapping

from jsonschema import Draft202012Validator


class SchemaValidationError(ValueError):
    """Raised when a boundary payload violates its JSON Schema contract."""


CANONICAL_TRANSACTION_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": [
        "tenant_id", "provider", "provider_account_id", "TransID", "TransAmount",
        "Currency", "TransactionType", "Status", "TransTime", "MSISDN",
    ],
    "properties": {
        "tenant_id": {"type": "string", "minLength": 1, "maxLength": 128},
        "provider": {"type": "string", "minLength": 1, "maxLength": 64},
        "provider_account_id": {"type": "string", "minLength": 1, "maxLength": 255},
        "TransID": {"type": "string", "minLength": 1, "maxLength": 255},
        "TransAmount": {"type": ["string", "number"], "pattern": "^[+]?[0-9]+(\\.[0-9]+)?$"},
        "Currency": {"type": "string", "pattern": "^[A-Z]{3}$"},
        "TransactionType": {"type": "string", "minLength": 1},
        "Status": {"type": "string", "minLength": 1},
        "TransTime": {"type": "string", "minLength": 1},
        "MSISDN": {"type": "string", "minLength": 1},
    },
    "additionalProperties": True,
}

EVENT_ENVELOPE_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": [
        "event_id", "event_type", "event_version", "occurred_at", "tenant_id",
        "aggregate_id", "payload", "correlation_id",
    ],
    "properties": {
        "event_id": {"type": "string", "minLength": 1},
        "event_type": {"type": "string", "minLength": 1},
        "event_version": {"type": "integer", "minimum": 1},
        "occurred_at": {"type": "string", "minLength": 1},
        "tenant_id": {"type": "string", "minLength": 1, "maxLength": 128},
        "aggregate_id": {"type": "string", "minLength": 1},
        "payload": {"type": "object"},
        "correlation_id": {"type": "string", "minLength": 1},
        "attempt": {"type": "integer", "minimum": 1},
        "max_attempts": {"type": "integer", "minimum": 1},
        "schema_version": {"type": "string", "minLength": 1},
        "source": {"type": "string", "minLength": 1},
        "producer": {"type": "string", "minLength": 1},
    },
    "additionalProperties": True,
}

AUDIT_EVENT_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://pesaguard.example/schemas/audit-event-1.0.json",
    "type": "object",
    "required": ["actor", "action", "resource", "timestamp"],
    "properties": {
        "actor": {"type": "object", "required": ["id", "type"], "properties": {"id": {"type": "string", "minLength": 1}, "type": {"type": "string", "minLength": 1}, "name": {"type": "string"}}, "additionalProperties": True},
        "action": {"type": "string", "minLength": 1},
        "resource": {"type": "object", "required": ["type", "id"], "properties": {"type": {"type": "string", "minLength": 1}, "id": {"type": "string", "minLength": 1}}, "additionalProperties": True},
        "timestamp": {"type": "string", "minLength": 1},
        "tenant_id": {"type": "string", "minLength": 1},
        "correlation_id": {"type": "string"},
        "before": {},
        "after": {},
        "metadata": {"type": "object"}
    },
    "additionalProperties": False
}


def _validate(payload: Mapping[str, Any], schema: Mapping[str, Any], boundary: str) -> None:
    errors = sorted(Draft202012Validator(schema).iter_errors(payload), key=lambda error: list(error.path))
    if errors:
        error = errors[0]
        location = ".".join(str(part) for part in error.path) or "$"
        raise SchemaValidationError(f"{boundary} schema validation failed at {location}: {error.message}")


def validate_canonical_transaction(payload: Mapping[str, Any]) -> None:
    _validate(payload, CANONICAL_TRANSACTION_SCHEMA, "canonical transaction")


def validate_event_envelope(payload: Mapping[str, Any]) -> None:
    _validate(payload, EVENT_ENVELOPE_SCHEMA, "event envelope")

def validate_audit_event(payload: Mapping[str, Any]) -> None:
    _validate(payload, AUDIT_EVENT_SCHEMA, "audit event")