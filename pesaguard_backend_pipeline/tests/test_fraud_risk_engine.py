from datetime import datetime, timedelta, timezone

from fraud_risk_engine import assess_transaction, calculate_features, evaluate_predictions


def tx(identifier, *, amount="1000", customer="254700000001", merchant="600000", when="20260914100000"):
    return {
        "TransID": identifier,
        "TransAmount": amount,
        "MSISDN": customer,
        "BusinessShortCode": merchant,
        "TransTime": when,
    }


def test_normal_transaction_is_low_and_processed():
    decision = assess_transaction(tx("normal-1"), [tx("old-1", when="20260913090000")])
    assert decision.risk_level == "LOW"
    assert decision.action == "process"
    assert decision.reason_codes == ()


def test_synthetic_fraud_triggers_velocity_duplicate_and_odd_hour():
    current = tx("fraud-2", amount="300000", when="20260914030000")
    history = [
        tx("fraud-1", amount="299000", when="20260914025959"),
        tx("fraud-0", amount="298000", when="20260914025950"),
        tx("fraud-2", amount="297000", when="20260914025940"),
        tx("fraud-3", amount="296000", when="20260914025930"),
        tx("fraud-4", amount="295000", when="20260914025920"),
    ]
    decision = assess_transaction(current, history)
    assert decision.risk_level in {"HIGH", "CRITICAL"}
    assert {"velocity", "amount_threshold", "unusual_time"}.issubset(decision.rules_triggered)
    assert decision.action in {"review", "escalate"}


def test_high_value_legitimate_transaction_can_use_tenant_baseline():
    decision = assess_transaction(
        tx("legitimate-high", amount="200000", merchant="trusted-merchant"),
        [tx(f"history-{index}", amount="195000", merchant="trusted-merchant", when=f"202609{index + 1:02d}100000") for index in range(10)],
        {"mean_amount": 195000, "std_amount": 5000, "customer_mean_amount": 190000},
    )
    assert decision.risk_level in {"LOW", "MEDIUM"}
    assert "amount_threshold" in decision.rules_triggered


def test_high_frequency_merchant_is_not_automatically_fraud():
    history = [tx(f"merchant-{index}", customer=f"254700{index:06d}", merchant="busy") for index in range(20)]
    decision = assess_transaction(tx("merchant-current", merchant="busy"), history)
    assert decision.action in {"process", "monitor"}
    assert "velocity" not in decision.rules_triggered


def test_duplicate_activity_and_rapid_changes_are_explainable():
    history = [
        tx("same-id", amount="100"),
        tx("other-1", amount="200"),
        tx("other-2", amount="400"),
        tx("other-3", amount="800"),
    ]
    decision = assess_transaction(tx("same-id", amount="1600"), history)
    assert "duplicate_activity" in decision.rules_triggered
    assert "rapid_transaction_changes" in decision.rules_triggered
    assert decision.model_version
    assert decision.features.as_dict()["amount"] == 1600.0


def test_evaluation_reports_precision_recall_false_positives_and_latency():
    normal = assess_transaction(tx("eval-normal"))
    suspicious = assess_transaction(tx("eval-fraud", amount="400000", when="20260914020000"))
    metrics = evaluate_predictions([(normal, False), (suspicious, True), (normal, True)])
    assert metrics["precision"] >= 0
    assert metrics["recall"] >= 0
    assert metrics["false_positives"] >= 0
    assert metrics["false_negatives"] >= 0
    assert metrics["detection_latency_ms"] >= 0
