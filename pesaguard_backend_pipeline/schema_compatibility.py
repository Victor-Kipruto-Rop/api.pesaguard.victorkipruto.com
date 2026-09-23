"""Backward-compatibility checks for versioned JSON Schema contracts."""

from __future__ import annotations

from dataclasses import dataclass
import argparse
import json
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class SchemaChange:
    path: str
    kind: str
    breaking: bool
    message: str


class IncompatibleSchemaError(ValueError):
    """Raised when a proposed schema cannot safely replace its predecessor."""

    def __init__(self, changes: list[SchemaChange]):
        self.changes = changes
        super().__init__("; ".join(change.message for change in changes if change.breaking))


def compare_schemas(old: Mapping[str, Any], new: Mapping[str, Any], *, path: str = "$") -> list[SchemaChange]:
    """Compare two schemas from a consumer backward-compatibility perspective."""
    changes: list[SchemaChange] = []
    old_properties = old.get("properties", {})
    new_properties = new.get("properties", {})
    old_required = set(old.get("required", []))
    new_required = set(new.get("required", []))

    for name in sorted(set(old_properties) - set(new_properties)):
        renamed_to = next((candidate for candidate, value in new_properties.items() if value.get("x-renamedFrom") == name), None)
        kind = "renamed" if renamed_to else "removed"
        message = f"renamed field {path}.{name} -> {path}.{renamed_to}" if renamed_to else f"removed field {path}.{name}"
        changes.append(SchemaChange(f"{path}.{name}", kind, True, message))
        if renamed_to:
            changes.extend(compare_schemas(old_properties[name], new_properties[renamed_to], path=f"{path}.{renamed_to}"))
    for name in sorted(old_required - new_required):
        changes.append(SchemaChange(f"{path}.{name}", "required_relaxed", False, f"field became optional: {path}.{name}"))
    for name in sorted(new_required - old_required):
        if name in old_properties:
            changes.append(SchemaChange(f"{path}.{name}", "required", True, f"field became required: {path}.{name}"))
        else:
            changes.append(SchemaChange(f"{path}.{name}", "required", True, f"new required field: {path}.{name}"))
    for name in sorted(set(old_properties) & set(new_properties)):
        changes.extend(compare_schemas(old_properties[name], new_properties[name], path=f"{path}.{name}"))

    old_type = old.get("type")
    new_type = new.get("type")
    if old_type is not None and new_type is not None and old_type != new_type:
        changes.append(SchemaChange(path, "type", True, f"type changed at {path}: {old_type!r} -> {new_type!r}"))

    old_enum = set(old.get("enum", []))
    new_enum = set(new.get("enum", []))
    if old_enum and new_enum and not old_enum.issubset(new_enum):
        changes.append(SchemaChange(path, "enum_removed", True, f"enum values removed at {path}: {sorted(old_enum - new_enum)}"))
    elif new_enum and not old_enum:
        changes.append(SchemaChange(path, "enum", True, f"enum constraint added at {path}"))

    for keyword, label in (("format", "format"), ("x-timezone", "timezone"), ("x-unit", "unit"), ("x-meaning", "meaning"), ("multipleOf", "precision/scale")):
        if keyword in old and keyword in new and old[keyword] != new[keyword]:
            changes.append(SchemaChange(path, label, True, f"{label} changed at {path}: {old[keyword]!r} -> {new[keyword]!r}"))

    for name in sorted(set(new_properties) - set(old_properties)):
        if name not in new_required:
            changes.append(SchemaChange(f"{path}.{name}", "added_optional", False, f"added optional field {path}.{name}"))
    return changes


def assert_backward_compatible(old: Mapping[str, Any], new: Mapping[str, Any]) -> list[SchemaChange]:
    """Return changes or raise when existing consumers may break."""
    changes = compare_schemas(old, new)
    breaking = [change for change in changes if change.breaking]
    if breaking:
        raise IncompatibleSchemaError(breaking)
    return changes


def compare_openapi(old: Mapping[str, Any], new: Mapping[str, Any]) -> list[SchemaChange]:
    """Detect removed API paths/methods/responses and changed component schemas."""
    changes: list[SchemaChange] = []
    old_paths = old.get("paths", {})
    new_paths = new.get("paths", {})
    for path in sorted(set(old_paths) - set(new_paths)):
        changes.append(SchemaChange(f"paths.{path}", "endpoint_removed", True, f"removed endpoint: {path}"))
    for path in sorted(set(old_paths) & set(new_paths)):
        old_methods = {key for key in old_paths[path] if key in {"get", "post", "put", "patch", "delete"}}
        new_methods = {key for key in new_paths[path] if key in {"get", "post", "put", "patch", "delete"}}
        for method in sorted(old_methods - new_methods):
            changes.append(SchemaChange(f"paths.{path}.{method}", "method_removed", True, f"removed method: {method.upper()} {path}"))
        for method in sorted(old_methods & new_methods):
            old_codes = set(old_paths[path][method].get("responses", {}))
            new_codes = set(new_paths[path][method].get("responses", {}))
            for code in sorted(old_codes - new_codes):
                changes.append(SchemaChange(f"paths.{path}.{method}.responses.{code}", "response_removed", True, f"removed response {code} from {method.upper()} {path}"))
    old_components = old.get("components", {}).get("schemas", {})
    new_components = new.get("components", {}).get("schemas", {})
    for name in sorted(set(old_components) & set(new_components)):
        changes.extend(compare_schemas(old_components[name], new_components[name], path=f"components.schemas.{name}"))
    return changes


def main() -> int:
    parser = argparse.ArgumentParser(description="Fail when a contract change breaks backward compatibility.")
    parser.add_argument("--old-openapi", type=Path, required=True)
    parser.add_argument("--new-openapi", type=Path, required=True)
    args = parser.parse_args()
    old = json.loads(args.old_openapi.read_text(encoding="utf-8"))
    new = json.loads(args.new_openapi.read_text(encoding="utf-8"))
    changes = compare_openapi(old, new)
    for change in changes:
        print(f"{'BREAKING' if change.breaking else 'SAFE'} {change.kind}: {change.message}")
    return 1 if any(change.breaking for change in changes) else 0


if __name__ == "__main__":
    raise SystemExit(main())