"""Common source-connector lifecycle for PesaGuard."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Iterable, Mapping

from ingestion import IngestionEnvelope, IngestionError, IngestionResult, ProviderAdapter


class Connector(ABC):
    """Provider-independent source contract."""

    source: str

    @abstractmethod
    def authenticate(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def fetch(self, payload: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def validate(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def transform(self, payload: Mapping[str, Any], *, tenant_id: str) -> IngestionEnvelope:
        raise NotImplementedError

    @abstractmethod
    def emit(self, envelope: IngestionEnvelope) -> IngestionResult:
        raise NotImplementedError

    def ingest(self, payload: Mapping[str, Any], *, tenant_id: str) -> list[IngestionResult]:
        if not self.authenticate():
            raise IngestionError(f"connector authentication failed: {self.source}")
        results = []
        for record in self.fetch(payload):
            validated = self.validate(record)
            envelope = self.transform(validated, tenant_id=tenant_id)
            results.append(self.emit(envelope))
        return results


class AdapterConnector(Connector):
    """Reusable connector lifecycle around a provider adapter."""

    def __init__(self, adapter: ProviderAdapter, ingestion_service: Any, credentials: Mapping[str, Any] | None = None):
        self.adapter = adapter
        self.ingestion_service = ingestion_service
        self.credentials = dict(credentials or {})
        self.source = adapter.provider

    def authenticate(self) -> bool:
        return bool(self.credentials.get("enabled", True))

    def fetch(self, payload: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
        return (payload,)

    def validate(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        if not isinstance(payload, Mapping):
            raise IngestionError(f"{self.source} connector payload must be an object")
        return payload

    def transform(self, payload: Mapping[str, Any], *, tenant_id: str) -> IngestionEnvelope:
        return self.adapter.normalize(payload, tenant_id=tenant_id)

    def emit(self, envelope: IngestionEnvelope) -> IngestionResult:
        return self.ingestion_service.emit(envelope)