import pytest

from lifecycle import InvalidLifecycleTransition, transition_discrepancy, transition_reconciliation


def test_reconciliation_lifecycle_allows_forward_progression():
    assert transition_reconciliation("pending", "processing") == "processing"
    assert transition_reconciliation("processing", "completed") == "completed"
    assert transition_reconciliation("failed", "processing") == "processing"


def test_reconciliation_lifecycle_rejects_regression():
    with pytest.raises(InvalidLifecycleTransition):
        transition_reconciliation("completed", "processing")


def test_discrepancy_lifecycle_rejects_resolution_regression():
    assert transition_discrepancy("needs_review", "reviewed") == "reviewed"
    with pytest.raises(InvalidLifecycleTransition):
        transition_discrepancy("resolved", "needs_review")
