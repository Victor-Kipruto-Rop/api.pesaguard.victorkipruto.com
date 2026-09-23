import pytest

from ingestion import IngestionError, IngestionService
from source_contracts import SourceContractError, validate_source_payload
from tests.test_ingestion import FakeEventStore


@pytest.mark.parametrize(
    "provider,payload,field",
    [
        ("airtel-money", {"transaction_id": "a-1", "amount": "1.00"}, "account_id"),
        ("bank", {"transaction_id": "b-1", "account_id": "acct"}, "amount"),
        ("pos", {"transaction_id": "p-1", "amount": "1.00", "merchant_id": "m-1"}, "terminal_id"),
    ],
)
def test_provider_contracts_reject_missing_required_fields(provider, payload, field):
    with pytest.raises(SourceContractError, match=field):
        validate_source_payload(provider, payload)


def test_mpesa_contract_rejects_malformed_phone():
    with pytest.raises(SourceContractError, match="MSISDN"):
        validate_source_payload("mpesa", {
            "TransactionType": "Pay Bill",
            "TransID": "mpesa-1",
            "TransTime": "20260923120000",
            "TransAmount": "10.00",
            "BusinessShortCode": "123456",
            "MSISDN": "0700000000",
        })


def test_invalid_source_contract_never_reaches_event_store():
    service = IngestionService(FakeEventStore())
    with pytest.raises(IngestionError, match="bank schema 1.0"):
        service.ingest("bank", {"transaction_id": "bank-1"}, tenant_id="tenant-a")