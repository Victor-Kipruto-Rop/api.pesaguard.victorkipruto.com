import pytest

from contract_versioning import UnsupportedContractVersion, validate_contract_version
from event_bus import EventContractError, build_event
from source_contracts import SourceContractError, validate_source_payload


def test_contract_versions_accept_current_and_reject_unknown_major():
    assert validate_contract_version("event", "1.0") == "1.0"
    with pytest.raises(UnsupportedContractVersion):
        validate_contract_version("event", "2.0")


def test_event_schema_version_is_enforced():
    with pytest.raises(EventContractError, match="unsupported event contract version"):
        build_event("transaction.received", "tenant-a", "tx-1", {}, schema_version="2.0")


def test_source_schema_version_is_enforced():
    payload = {"transaction_id": "tx-1", "amount": "1.00", "account_id": "acct", "schema_version": "2.0"}
    with pytest.raises(SourceContractError, match="unsupported bank contract version"):
        validate_source_payload("bank", payload)