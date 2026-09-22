"""M-Pesa and Safaricom source connectors."""

from ingestion import MpesaAdapter, SafaricomApiAdapter
from connectors.base import AdapterConnector


class MpesaConnector(AdapterConnector):
    def __init__(self, ingestion_service, credentials=None):
        super().__init__(MpesaAdapter(), ingestion_service, credentials)


class SafaricomConnector(AdapterConnector):
    def __init__(self, ingestion_service, credentials=None):
        super().__init__(SafaricomApiAdapter(), ingestion_service, credentials)


__all__ = ["MpesaConnector", "SafaricomConnector"]