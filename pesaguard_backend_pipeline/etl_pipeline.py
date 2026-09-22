"""ETL and ELT orchestration over immutable PesaGuard raw objects."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, Mapping, Optional

from batch_ingestion import ObjectStorage, _records_from_bytes
from ingestion import IngestionResult, IngestionService


@dataclass(frozen=True)
class RawDataset:
    """Immutable raw object reference shared by ETL and ELT workflows."""

    tenant_id: str
    dataset_id: str
    filename: str
    object_key: str
    content_hash: str


class RawDatasetLoader:
    """Load source bytes without transforming or overwriting them."""

    def __init__(self, storage: Optional[ObjectStorage] = None):
        self.storage = storage or ObjectStorage()

    def load(self, *, tenant_id: str, dataset_id: str, filename: str, content: bytes) -> RawDataset:
        object_key = self.storage.put(tenant_id, dataset_id, filename, content)
        content_hash = hashlib.sha256(content).hexdigest()
        return RawDataset(tenant_id, dataset_id, filename, object_key, content_hash)

    def read(self, dataset: RawDataset) -> bytes:
        content = self.storage.get(dataset.object_key)
        if hashlib.sha256(content).hexdigest() != dataset.content_hash:
            raise ValueError("raw dataset integrity check failed")
        return content


class ETLPipeline:
    """Extract, transform, then load canonical rows into operational state."""

    def __init__(self, loader: RawDatasetLoader, ingestion_service: IngestionService):
        self.loader = loader
        self.ingestion_service = ingestion_service

    def run(self, dataset: RawDataset, *, source: str) -> list[IngestionResult]:
        results = []
        for record in _records_from_bytes(dataset.filename, self.loader.read(dataset)):
            results.append(self.ingestion_service.ingest(source, record, tenant_id=dataset.tenant_id))
        return results


class ELTPipeline:
    """Load raw data first, then transform it inside the platform on demand."""

    def __init__(self, loader: RawDatasetLoader):
        self.loader = loader

    def transform_loaded(
        self,
        dataset: RawDataset,
        transform: Callable[[Mapping[str, Any]], Mapping[str, Any]],
    ) -> Iterable[Mapping[str, Any]]:
        for record in _records_from_bytes(dataset.filename, self.loader.read(dataset)):
            yield transform(record)