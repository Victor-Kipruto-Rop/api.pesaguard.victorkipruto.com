"""Point-of-sale source connector."""

from connectors.base import AdapterConnector
from ingestion import PosAdapter


class PosConnector(AdapterConnector):
    def __init__(self, ingestion_service, credentials=None):
        super().__init__(PosAdapter(), ingestion_service, credentials)


__all__ = ["PosConnector"]