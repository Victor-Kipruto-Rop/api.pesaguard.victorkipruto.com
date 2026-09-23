from ingestion import IngestionError, IngestionService, ProcessResult


def mpesa_payload(reference="R-1"):
    return {
        "TransactionType": "Pay Bill",
        "TransID": reference,
        "TransTime": "20260923120000",
        "TransAmount": "10.50",
        "BusinessShortCode": "123456",
        "MSISDN": "254700000000",
    }


class FakeEventStore:
    def __init__(self):
        self.calls = []
        self.seen = set()

    def mark_processed(self, payload, *, tenant_id, idempotency_key_override):
        self.calls.append((payload, tenant_id, idempotency_key_override))
        if idempotency_key_override in self.seen:
            return ProcessResult.DUPLICATE
        self.seen.add(idempotency_key_override)
        return ProcessResult.STORED


def test_all_source_adapters_share_one_envelope_contract():
    service = IngestionService(FakeEventStore())
    records = {
        "mpesa": mpesa_payload(),
        "airtel-money": {"transaction_id": "airtel-1", "amount": "4.25", "account_id": "airtel-acct"},
        "bank": {"transaction_id": "bank-1", "amount": "8.00", "account_id": "bank-acct"},
        "pos": {"transaction_id": "pos-1", "amount": "2.00", "account_id": "pos-acct", "merchant_id": "merchant-1", "terminal_id": "terminal-1"},
        "csv": {"transaction_id": "csv-1", "amount": "3.00", "account_id": "file-1"},
        "external-api": {"transaction_id": "api-1", "amount": "5.00", "account_id": "api-1"},
        "webhook": {"transaction_id": "hook-1", "amount": "6.00", "account_id": "hook-1"},
    }
    for provider, payload in records.items():
        result = service.ingest(provider, payload, tenant_id="tenant-a")
        assert result.envelope.provider == provider
        assert result.envelope.tenant_id == "tenant-a"
        assert result.envelope.external_reference
        assert result.envelope.schema_version == 1


def test_ingestion_service_uses_store_for_idempotency_without_direct_table_access():
    store = FakeEventStore()
    service = IngestionService(store)
    first = service.ingest("mpesa", mpesa_payload(), tenant_id="tenant-a")
    second = service.ingest("mpesa", mpesa_payload(), tenant_id="tenant-a")
    assert first.result is ProcessResult.STORED
    assert second.result is ProcessResult.DUPLICATE
    assert len(store.calls) == 2
    assert all(call[1] == "tenant-a" for call in store.calls)


def test_unknown_provider_and_invalid_payload_are_rejected():
    service = IngestionService(FakeEventStore())
    try:
        service.ingest("unknown", {}, tenant_id="tenant-a")
    except IngestionError as error:
        assert "unsupported" in str(error)
    else:
        raise AssertionError("unknown providers must not bypass the adapter registry")

    try:
        service.ingest("bank", {"transaction_id": "bank-2"}, tenant_id="tenant-a")
    except IngestionError as error:
        assert "amount" in str(error)
    else:
        raise AssertionError("invalid records must be rejected before persistence")


def test_safaricom_api_adapter_maps_provider_fields_at_boundary():
    service = IngestionService(FakeEventStore())
    result = service.ingest(
        "safaricom-api",
        {
            "data": {
                "transactionId": "QWE123",
                "amount": 2500,
                "currency": "KES",
                "accountId": "acc-123",
                "phoneNumber": "254700000000",
                "transactionTime": "2026-09-23T18:29:54Z",
            }
        },
        tenant_id="tenant-a",
    )
    assert result.envelope.canonical.transaction_id.startswith("txn_")
    assert result.envelope.canonical.provider_transaction_id == "QWE123"
    assert result.envelope.canonical.amount == "2500.00"
    assert result.envelope.canonical.provider == "safaricom"
    assert "transactionId" not in result.envelope.canonical.__dict__
    assert result.envelope.payload["TransID"] == "QWE123"