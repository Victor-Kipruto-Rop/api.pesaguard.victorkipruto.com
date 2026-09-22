"""CSV/file source connector."""

from connectors.base import AdapterConnector
from ingestion import CsvAdapter


class FileConnector(AdapterConnector):
    def __init__(self, ingestion_service, credentials=None):
        super().__init__(CsvAdapter(), ingestion_service, credentials)


__all__ = ["FileConnector"]