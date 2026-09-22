from __future__ import annotations

from .enums import NotificationStatus


class InvalidNotificationTransition(ValueError):
    """Raised when a notification lifecycle update is not allowed."""


_TRANSITIONS: dict[NotificationStatus, frozenset[NotificationStatus]] = {
    NotificationStatus.CREATED: frozenset({NotificationStatus.QUEUED, NotificationStatus.CANCELLED}),
    NotificationStatus.QUEUED: frozenset({NotificationStatus.PROCESSING, NotificationStatus.CANCELLED, NotificationStatus.EXPIRED}),
    NotificationStatus.PROCESSING: frozenset({
        NotificationStatus.ACCEPTED,
        NotificationStatus.SUBMITTED,
        NotificationStatus.FAILED,
        NotificationStatus.REJECTED,
        NotificationStatus.RETRYING,
        NotificationStatus.CANCELLED,
        NotificationStatus.EXPIRED,
    }),
    NotificationStatus.ACCEPTED: frozenset({
        NotificationStatus.SUBMITTED,
        NotificationStatus.DELIVERED,
        NotificationStatus.OPENED,
        NotificationStatus.CLICKED,
        NotificationStatus.BOUNCED,
        NotificationStatus.COMPLAINED,
        NotificationStatus.FAILED,
        NotificationStatus.EXPIRED,
    }),
    NotificationStatus.SUBMITTED: frozenset({
        NotificationStatus.DELIVERED,
        NotificationStatus.OPENED,
        NotificationStatus.CLICKED,
        NotificationStatus.BOUNCED,
        NotificationStatus.COMPLAINED,
        NotificationStatus.FAILED,
        NotificationStatus.EXPIRED,
    }),
    NotificationStatus.SENT: frozenset({
        NotificationStatus.DELIVERED,
        NotificationStatus.OPENED,
        NotificationStatus.CLICKED,
        NotificationStatus.BOUNCED,
        NotificationStatus.COMPLAINED,
        NotificationStatus.FAILED,
        NotificationStatus.EXPIRED,
    }),
    NotificationStatus.DELIVERED: frozenset({NotificationStatus.OPENED, NotificationStatus.CLICKED}),
    NotificationStatus.OPENED: frozenset({NotificationStatus.CLICKED}),
    NotificationStatus.CLICKED: frozenset(),
    NotificationStatus.BOUNCED: frozenset(),
    NotificationStatus.COMPLAINED: frozenset(),
    NotificationStatus.RETRYING: frozenset({NotificationStatus.PROCESSING, NotificationStatus.DEAD_LETTER, NotificationStatus.CANCELLED}),
    NotificationStatus.FAILED: frozenset({NotificationStatus.RETRYING, NotificationStatus.DEAD_LETTER}),
    NotificationStatus.REJECTED: frozenset(),
    NotificationStatus.EXPIRED: frozenset(),
    NotificationStatus.CANCELLED: frozenset(),
    NotificationStatus.DEAD_LETTER: frozenset({NotificationStatus.QUEUED}),
}


def can_transition(current: str | NotificationStatus, target: str | NotificationStatus) -> bool:
    current_status = NotificationStatus(current)
    target_status = NotificationStatus(target)
    return current_status == target_status or target_status in _TRANSITIONS[current_status]


def transition(current: str | NotificationStatus, target: str | NotificationStatus) -> str:
    current_status = NotificationStatus(current)
    target_status = NotificationStatus(target)
    if not can_transition(current_status, target_status):
        raise InvalidNotificationTransition(
            f"notification cannot transition from {current_status.value} to {target_status.value}"
        )
    return target_status.value
