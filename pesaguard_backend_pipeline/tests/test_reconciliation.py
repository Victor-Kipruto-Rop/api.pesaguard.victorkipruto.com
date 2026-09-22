from reconciliation_engine import evaluate_transaction


def make_event(trans_id="T1", amount="100", phone="254700000000", trans_time="20240601120000"):
    return {
        "TransID": trans_id,
        "TransAmount": amount,
        "MSISDN": phone,
        "TransTime": trans_time,
        "BusinessShortCode": "12345",
    }


def make_internal_record(internal_ref="ORD-1", amount=100.0, phone="254700000000", timestamp="2024-06-01T12:00:00Z", status="pending"):
    return {
        "internal_ref": internal_ref,
        "amount": amount,
        "phone_number": phone,
        "timestamp": timestamp,
        "status": status,
    }


def test_exact_match_is_resolved():
    event = make_event(trans_id="T-100", amount="100", phone="254700000000", trans_time="20240601120000")
    internal_record = make_internal_record(timestamp="2024-06-01T12:00:00Z")

    result = evaluate_transaction(event, [internal_record], seen_trans_ids=set())

    assert result["status"] == "matched"
    assert result["severity"] == "info"
    assert result["match"]["match_type"] == "exact"


def test_partial_match_is_review_required():
    event = make_event(trans_id="T-200", amount="100", phone="254700000001", trans_time="20240601120000")
    internal_record = make_internal_record(internal_ref="ORD-2", phone="254700000000", timestamp="2024-06-01T12:00:00Z")

    result = evaluate_transaction(event, [internal_record], seen_trans_ids=set())

    assert result["status"] == "needs_review"
    assert result["severity"] == "warning"
    assert result["match"]["match_type"] in {"partial", "partial_fuzzy"}


def test_missing_payment_is_critical():
    event = make_event(trans_id="T-300", amount="100", phone="254700000002", trans_time="20240601130000")
    internal_record = make_internal_record(internal_ref="ORD-3", phone="254700000002", amount=100.0, timestamp="2024-06-01T11:00:00Z")

    result = evaluate_transaction(event, [internal_record], seen_trans_ids=set(), window_minutes=15)

    assert result["status"] == "missing_payment"
    assert result["severity"] == "critical"


def test_duplicate_transaction_is_flagged_without_double_alerting():
    event = make_event(trans_id="T-400", amount="100", phone="254700000003", trans_time="20240601120000")
    internal_record = make_internal_record(internal_ref="ORD-4", phone="254700000003", timestamp="2024-06-01T12:00:00Z")

    result = evaluate_transaction(event, [internal_record], seen_trans_ids={"T-400"})

    assert "duplicate_transaction_id" in result["anomalies"]
    assert result["duplicate"] is True
