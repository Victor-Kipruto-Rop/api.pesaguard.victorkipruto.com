"""Central PesaGuard data-asset catalog registry."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping, Optional


class CatalogError(ValueError):
    """Raised when a catalog asset is incomplete or unknown."""


@dataclass(frozen=True)
class DatasetAsset:
    name: str
    description: str
    owner: str
    schema: Mapping[str, str]
    source: str
    sensitivity: str
    retention: str
    refresh_frequency: str
    quality_score: Optional[float]
    lineage: str
    consumers: tuple[str, ...]

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "DatasetAsset":
        required = ("name", "description", "owner", "schema", "source", "sensitivity", "retention", "refresh_frequency", "lineage", "consumers")
        missing = [key for key in required if not value.get(key)]
        if missing:
            raise CatalogError(f"dataset catalog entry missing fields: {', '.join(missing)}")
        score = value.get("quality_score")
        if score is not None and not 0 <= float(score) <= 1:
            raise CatalogError(f"quality_score for {value['name']} must be between 0 and 1")
        return cls(
            name=str(value["name"]),
            description=str(value["description"]),
            owner=str(value["owner"]),
            schema=dict(value["schema"]),
            source=str(value["source"]),
            sensitivity=str(value["sensitivity"]),
            retention=str(value["retention"]),
            refresh_frequency=str(value["refresh_frequency"]),
            quality_score=float(score) if score is not None else None,
            lineage=str(value["lineage"]),
            consumers=tuple(str(item) for item in value["consumers"]),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "owner": self.owner,
            "schema": dict(self.schema),
            "source": self.source,
            "sensitivity": self.sensitivity,
            "retention": self.retention,
            "refresh_frequency": self.refresh_frequency,
            "quality_score": self.quality_score,
            "lineage": self.lineage,
            "consumers": list(self.consumers),
        }


class DataCatalog:
    def __init__(self, assets: Mapping[str, DatasetAsset], *, version: str = "1.0"):
        if not assets:
            raise CatalogError("data catalog must contain at least one dataset")
        self.assets = dict(assets)
        self.version = version

    def dataset(self, name: str) -> DatasetAsset:
        try:
            return self.assets[name]
        except KeyError as exc:
            raise CatalogError(f"dataset is not registered: {name}") from exc

    def list(self) -> list[DatasetAsset]:
        return [self.assets[name] for name in sorted(self.assets)]

    @classmethod
    def from_file(cls, path: str | Path) -> "DataCatalog":
        try:
            document = json.loads(Path(path).read_text(encoding="utf-8"))
            assets = {item["name"]: DatasetAsset.from_dict(item) for item in document["datasets"]}
            return cls(assets, version=str(document.get("version", "1.0")))
        except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
            raise CatalogError(f"could not load data catalog: {path}") from exc


def load_catalog(path: Optional[str] = None) -> DataCatalog:
    return DataCatalog.from_file(path or Path(__file__).with_name("data_catalog.json"))