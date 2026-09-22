from enrichment_service import EnrichmentService, HistoricalStatistics
from ingestion import CanonicalTransaction


def test_enrichment_adds_merchant_customer_history_risk_device_and_frequency():
    transaction = CanonicalTransaction(
        tenant_id="tenant-a",
        provider="mpesa",
        provider_account_id="acct-1",
        transaction_id="txn-1",
        provider_transaction_id="MP-1",
        account_id="acct-1",
        amount="5000.00",
        currency="KES",
        transaction_type="PAYMENT",
        status="RECEIVED",
        transaction_time="2026-09-23T00:00:00Z",
        phone_number="+254700000000",
        merchant_id="merchant-1",
        metadata={"location": {"country_code": "KE", "city": "Nairobi"}},
    )
    service = EnrichmentService(
        merchant_lookup=lambda tenant, merchant: {"id": merchant, "tier": "gold"},
        customer_lookup=lambda tenant, phone: {"phone": phone, "segment": "sacco"},
        account_lookup=lambda tenant, account: {"id": account, "status": "active"},
        history_lookup=lambda tenant, item: HistoricalStatistics(transaction_count=12, average_amount="850.00", frequency_per_hour=4.5),
        risk_lookup=lambda tenant, item: {"score": 0.12, "level": "LOW"},
        device_lookup=lambda tenant, item: {"device_id": "device-1", "trusted": True},
    )
    payload = service.to_payload(service.enrich(transaction))
    assert payload["merchant"]["tier"] == "gold"
    assert payload["customer"]["segment"] == "sacco"
    assert payload["historical"]["transaction_count"] == 12
    assert payload["risk_profile"]["level"] == "LOW"
    assert payload["device"]["trusted"] is True
    assert payload["transaction_frequency"] == 4.5