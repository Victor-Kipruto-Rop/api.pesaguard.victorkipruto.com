"""Airtel Money source connector."""

from connectors.base import AdapterConnector
from ingestion import AirtelMoneyAdapter


class AirtelConnector(AdapterConnector):
    def __init__(self, ingestion_service, credentials=None):
        super().__init__(AirtelMoneyAdapter(), ingestion_service, credentials)


__all__ = ["AirtelConnector"]