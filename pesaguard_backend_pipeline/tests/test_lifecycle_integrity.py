import pytest

from lifecycle import InvalidLifecycleTransition, transition_data_lifecycle, transition_discrepancy, transition_reconciliation


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


def test_data_lifecycle_requires_archive_before_delete():
    assert transition_data_lifecycle("CREATED", "INGESTED") == "INGESTED"
    assert transition_data_lifecycle("CONSUMED", "ARCHIVED") == "ARCHIVED"
    assert transition_data_lifecycle("ARCHIVED", "DELETED") == "DELETED"
    with pytest.raises(InvalidLifecycleTransition):
        transition_data_lifecycle("CONSUMED", "DELETED")


def test_invalid_data_can_be_quarantined_and_then_deleted():
    assert transition_data_lifecycle("INGESTED", "QUARANTINED") == "QUARANTINED"
    assert transition_data_lifecycle("QUARANTINED", "DELETED") == "DELETED"
