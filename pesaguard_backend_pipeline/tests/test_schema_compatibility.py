import pytest

from schema_compatibility import IncompatibleSchemaError, assert_backward_compatible, compare_openapi, compare_schemas


def _schema(**kwargs):
    return {"type": "object", "properties": {"id": {"type": "string"}}, **kwargs}


def test_optional_field_addition_is_backward_compatible():
    changes = assert_backward_compatible(_schema(), _schema(properties={"id": {"type": "string"}, "metadata": {"type": "object"}}))
    assert any(change.kind == "added_optional" for change in changes)


@pytest.mark.parametrize(
    "old,new,expected",
    [
        (_schema(), _schema(properties={}), "removed field"),
        (_schema(), _schema(required=["id"]), "field became required"),
        (_schema(), _schema(properties={"id": {"type": "integer"}}), "type changed"),
        (_schema(properties={"id": {"type": "string", "enum": ["a", "b"]}}), _schema(properties={"id": {"type": "string", "enum": ["a"]}}), "enum values removed"),
    ],
)
def test_breaking_changes_require_explicit_review(old, new, expected):
    with pytest.raises(IncompatibleSchemaError, match=expected):
        assert_backward_compatible(old, new)


def test_compatibility_report_can_be_used_for_migration_review():
    changes = compare_schemas(_schema(), _schema(properties={"id": {"type": "string"}, "new": {"type": "number"}}))
    assert changes[0].breaking is False


def test_numeric_temporal_and_rename_changes_are_breaking():
    old = {"type": "object", "properties": {"amount": {"type": "number", "multipleOf": 0.01, "x-unit": "KES"}, "created_at": {"type": "string", "format": "date-time"}}}
    new = {"type": "object", "properties": {"amount": {"type": "number", "multipleOf": 0.001, "x-unit": "USD"}, "created": {"type": "string", "format": "date", "x-renamedFrom": "created_at"}}}
    changes = compare_schemas(old, new)
    assert {change.kind for change in changes} >= {"renamed", "precision/scale", "unit", "format"}
    with pytest.raises(IncompatibleSchemaError):
        assert_backward_compatible(old, new)


def test_openapi_gate_detects_removed_endpoint_method_and_response():
    old = {"paths": {"/transactions": {"get": {"responses": {"200": {}}}, "post": {"responses": {"200": {}}}}}}
    new = {"paths": {"/transactions": {"post": {"responses": {}}}}}
    changes = compare_openapi(old, new)
    assert {change.kind for change in changes} == {"method_removed", "response_removed"}