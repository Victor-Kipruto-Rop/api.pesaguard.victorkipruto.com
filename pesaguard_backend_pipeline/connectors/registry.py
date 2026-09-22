"""Connector registry replacing provider conditionals in callers."""

from __future__ import annotations

from typing import Any, Callable, Dict

from connectors.airtel import AirtelConnector
from connectors.banks import BankConnector
from connectors.files import FileConnector
from connectors.mpesa import MpesaConnector, SafaricomConnector
from connectors.pos import PosConnector


def connector_factories(ingestion_service: Any) -> Dict[str, Callable[..., Any]]:
    return {
        "mpesa": lambda credentials=None: MpesaConnector(ingestion_service, credentials),
        "safaricom-api": lambda credentials=None: SafaricomConnector(ingestion_service, credentials),
        "airtel-money": lambda credentials=None: AirtelConnector(ingestion_service, credentials),
        "bank": lambda credentials=None: BankConnector(ingestion_service, credentials),
        "pos": lambda credentials=None: PosConnector(ingestion_service, credentials),
        "csv": lambda credentials=None: FileConnector(ingestion_service, credentials),
    }


def get_connector(source: str, ingestion_service: Any, credentials=None):
    factory = connector_factories(ingestion_service).get(str(source).strip().lower())
    if factory is None:
        raise ValueError(f"unsupported connector source: {source}")
    return factory(credentials)