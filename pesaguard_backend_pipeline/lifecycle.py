"""Explicit financial and reconciliation lifecycle transition rules."""

from __future__ import annotations

from typing import Final


class InvalidLifecycleTransition(ValueError):
    """Raised when a financial record attempts an illegal state change."""


TRANSACTION_STATES: Final[tuple[str, ...]] = (
    "RECEIVED", "VALIDATED", "PROCESSING", "RECONCILING", "RECONCILED", "FAILED", "REJECTED",
)

TRANSACTION_TRANSITIONS: Final[dict[str, frozenset[str]]] = {
    "RECEIVED": frozenset({"VALIDATED", "FAILED", "REJECTED"}),
    "VALIDATED": frozenset({"PROCESSING", "FAILED"}),
    "PROCESSING": frozenset({"RECONCILING", "FAILED"}),
    "RECONCILING": frozenset({"RECONCILED", "FAILED"}),
    "RECONCILED": frozenset(),
    "FAILED": frozenset({"PROCESSING"}),
    "REJECTED": frozenset(),
}


RECONCILIATION_TRANSITIONS: Final[dict[str, frozenset[str]]] = {
    "pending": frozenset({"processing", "failed"}),
    "processing": frozenset({"completed", "failed"}),
    "failed": frozenset({"processing"}),
    "completed": frozenset(),
}

DISCREPANCY_TRANSITIONS: Final[dict[str, frozenset[str]]] = {
    "needs_review": frozenset({"reviewed", "escalated"}),
    "reviewed": frozenset({"resolved", "escalated"}),
    "escalated": frozenset({"reviewed", "resolved"}),
    "resolved": frozenset(),
}


def transition(current: str, target: str, transitions: dict[str, frozenset[str]]) -> str:
    if current == target:
        return target
    if target not in transitions.get(current, frozenset()):
        raise InvalidLifecycleTransition(f"invalid lifecycle transition: {current} -> {target}")
    return target


def transition_reconciliation(current: str, target: str) -> str:
    return transition(current, target, RECONCILIATION_TRANSITIONS)


def transition_transaction(current: str, target: str) -> str:
    return transition(current, target, TRANSACTION_TRANSITIONS)


def transition_discrepancy(current: str, target: str) -> str:
    return transition(current, target, DISCREPANCY_TRANSITIONS)
