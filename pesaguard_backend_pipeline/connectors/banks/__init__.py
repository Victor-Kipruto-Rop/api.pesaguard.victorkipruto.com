"""Bank statement and bank API source connector."""

from connectors.base import AdapterConnector
from ingestion import BankAdapter


class BankConnector(AdapterConnector):
    def __init__(self, ingestion_service, credentials=None):
        super().__init__(BankAdapter(), ingestion_service, credentials)


__all__ = ["BankConnector"]