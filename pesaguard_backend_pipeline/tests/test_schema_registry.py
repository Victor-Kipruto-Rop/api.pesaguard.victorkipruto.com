import json
from pathlib import Path

from jsonschema import Draft202012Validator


def test_schema_registry_files_are_machine_readable_and_structurally_valid():
    schema_dir = Path(__file__).parents[1] / "schemas"
    registry = json.loads((schema_dir / "registry.json").read_text(encoding="utf-8"))

    assert registry["format"] == "json-schema-draft-2020-12"
    for filename in registry["schemas"]:
        schema = json.loads((schema_dir / filename).read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        assert schema["$schema"].endswith("draft/2020-12/schema")
        assert "\\$defs" not in json.dumps(schema)