"""Tests for statistical/ML anomaly scoring functionality."""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from anomaly_rules import score_transaction_anomaly, check_for_anomalies

def test_anomaly_scoring_standard():
    # standard low transaction
    event = {"TransID": "A1", "TransAmount": "5000", "TransTime": "20260715120000"}
    score = score_transaction_anomaly(event)
    assert score < 0.5
    anomalies = check_for_anomalies(event, set())
    assert not any("high_anomaly_score" in a for a in anomalies)

def test_anomaly_scoring_highly_anomalous():
    # very high amount + off-hours + odd value
    event = {"TransID": "A2", "TransAmount": "260123", "TransTime": "20260715010000"}
    score = score_transaction_anomaly(event)
    assert score >= 0.8
    anomalies = check_for_anomalies(event, set())
    assert any("high_anomaly_score" in a for a in anomalies)
