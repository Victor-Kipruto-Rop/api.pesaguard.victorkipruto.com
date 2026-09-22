"""Field-level PesaGuard data dictionary."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from data_catalog import DataCatalog, CatalogError, load_catalog


class DictionaryError(ValueError):
    """Raised when a field definition is incomplete or unlinked."""


@dataclass(frozen=True)
class FieldDefinition:
    dataset: str
    field: str
    type: str
    nullable: bool
    description: str
    currency: Optional[str]
    constraints: tuple[str, ...]
    source: str
    pii: str
    used_by: tuple[str, ...]

    @classmethod
    def from_dict(cls, dataset: str, value: Mapping[str, Any]) -> "FieldDefinition":
        required = ("field", "type", "nullable", "description", "constraints", "source", "pii", "used_by")
        missing = [key for key in required if key not in value or value[key] in (None, "")]
        if missing:
            raise DictionaryError(f"{dataset} field definition missing: {', '.join(missing)}")
        return cls(
            dataset=dataset,
            field=str(value["field"]),
            type=str(value["type"]),
            nullable=bool(value["nullable"]),
            description=str(value["description"]),
            currency=str(value["currency"]) if value.get("currency") else None,
            constraints=tuple(str(item) for item in value["constraints"]),
            source=str(value["source"]),
            pii=str(value["pii"]),
            used_by=tuple(str(item) for item in value["used_by"]),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dataset": self.dataset,
            "field": self.field,
            "type": self.type,
            "nullable": self.nullable,
            "description": self.description,
            "currency": self.currency,
            "constraints": list(self.constraints),
            "source": self.source,
            "pii": self.pii,
            "used_by": list(self.used_by),
        }


class DataDictionary:
    def __init__(self, fields: Mapping[str, tuple[FieldDefinition, ...]], catalog: DataCatalog):
        self.fields = dict(fields)
        self.catalog = catalog
        unknown = set(self.fields) - set(catalog.assets)
        if unknown:
            raise DictionaryError(f"dictionary datasets missing from catalog: {', '.join(sorted(unknown))}")

    def dataset(self, dataset: str) -> tuple[FieldDefinition, ...]:
        if dataset not in self.fields:
            raise DictionaryError(f"dataset is not in dictionary: {dataset}")
        return self.fields[dataset]

    def field(self, dataset: str, field_name: str) -> FieldDefinition:
        for definition in self.dataset(dataset):
            if definition.field == field_name:
                return definition
        raise DictionaryError(f"field is not in dictionary: {dataset}.{field_name}")

    @classmethod
    def from_file(cls, path: str | Path, *, catalog: Optional[DataCatalog] = None) -> "DataDictionary":
        try:
            document = json.loads(Path(path).read_text(encoding="utf-8"))
            fields = {
                dataset: tuple(FieldDefinition.from_dict(dataset, field) for field in definitions)
                for dataset, definitions in document["datasets"].items()
            }
        except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
            raise DictionaryError(f"could not load data dictionary: {path}") from exc
        return cls(fields, catalog or load_catalog())


def load_dictionary(path: Optional[str] = None, *, catalog: Optional[DataCatalog] = None) -> DataDictionary:
    return DataDictionary.from_file(path or Path(__file__).with_name("data_dictionary.json"), catalog=catalog)