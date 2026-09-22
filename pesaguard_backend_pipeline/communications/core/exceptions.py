from __future__ import annotations


class CommunicationError(RuntimeError):
    """Base error for communication operations."""

    def __init__(self, message: str, *, code: str, retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.retryable = retryable


class TransientCommunicationError(CommunicationError):
    def __init__(self, message: str, *, code: str = "PROVIDER_UNAVAILABLE"):
        super().__init__(message, code=code, retryable=True)


class PermanentCommunicationError(CommunicationError):
    def __init__(self, message: str, *, code: str = "COMMUNICATION_REJECTED"):
        super().__init__(message, code=code, retryable=False)
