from __future__ import annotations

from enum import StrEnum


class ProviderErrorCategory(StrEnum):
    VALIDATION_ERROR = "VALIDATION_ERROR"
    AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR"
    AUTHORIZATION_ERROR = "AUTHORIZATION_ERROR"
    RATE_LIMITED = "RATE_LIMITED"
    TIMEOUT = "TIMEOUT"
    NETWORK_ERROR = "NETWORK_ERROR"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    INVALID_RECIPIENT = "INVALID_RECIPIENT"
    INSUFFICIENT_BALANCE = "INSUFFICIENT_BALANCE"
    MESSAGE_REJECTED = "MESSAGE_REJECTED"
    PERMANENT_FAILURE = "PERMANENT_FAILURE"
    UNKNOWN = "UNKNOWN"


_RETRYABLE = frozenset({
    ProviderErrorCategory.RATE_LIMITED,
    ProviderErrorCategory.TIMEOUT,
    ProviderErrorCategory.NETWORK_ERROR,
    ProviderErrorCategory.PROVIDER_UNAVAILABLE,
})


def is_retryable(category: str | ProviderErrorCategory) -> bool:
    return ProviderErrorCategory(category) in _RETRYABLE


def classify_provider_error(code: str | None, message: str | None = None) -> ProviderErrorCategory:
    value = f"{code or ''} {message or ''}".casefold()
    if any(token in value for token in ("timeout", "timed out")):
        return ProviderErrorCategory.TIMEOUT
    if any(token in value for token in ("429", "rate limit", "throttle")):
        return ProviderErrorCategory.RATE_LIMITED
    if any(token in value for token in ("401", "auth", "credential")):
        return ProviderErrorCategory.AUTHENTICATION_ERROR
    if any(token in value for token in ("403", "forbidden", "permission")):
        return ProviderErrorCategory.AUTHORIZATION_ERROR
    if any(token in value for token in ("balance", "credit")):
        return ProviderErrorCategory.INSUFFICIENT_BALANCE
    if any(token in value for token in ("recipient", "phone", "number")):
        return ProviderErrorCategory.INVALID_RECIPIENT
    if any(token in value for token in ("network", "connection", "dns")):
        return ProviderErrorCategory.NETWORK_ERROR
    if any(token in value for token in ("unavailable", "503", "service")):
        return ProviderErrorCategory.PROVIDER_UNAVAILABLE
    if any(token in value for token in ("reject", "invalid", "bad request")):
        return ProviderErrorCategory.MESSAGE_REJECTED
    return ProviderErrorCategory.UNKNOWN


# Maps internal provider-adapter error codes onto standardized categories so
# business logic never depends on provider-specific error strings.
_ADAPTER_CODE_CATEGORIES: dict[str, ProviderErrorCategory] = {
    "PROVIDER_TIMEOUT": ProviderErrorCategory.TIMEOUT,
    "PROVIDER_REQUEST_ERROR": ProviderErrorCategory.NETWORK_ERROR,
    "PROVIDER_NOT_CONFIGURED": ProviderErrorCategory.AUTHENTICATION_ERROR,
    "PROVIDER_REJECTED": ProviderErrorCategory.MESSAGE_REJECTED,
    "PROVIDER_UNAVAILABLE": ProviderErrorCategory.PROVIDER_UNAVAILABLE,
    "PROVIDER_RATE_LIMITED": ProviderErrorCategory.RATE_LIMITED,
    "INVALID_RECIPIENT": ProviderErrorCategory.INVALID_RECIPIENT,
    "CHANNEL_UNSUPPORTED": ProviderErrorCategory.VALIDATION_ERROR,
    "COMMUNICATION_REJECTED": ProviderErrorCategory.MESSAGE_REJECTED,
    "INSUFFICIENT_BALANCE": ProviderErrorCategory.INSUFFICIENT_BALANCE,
    "PERMANENT_FAILURE": ProviderErrorCategory.PERMANENT_FAILURE,
    "VALIDATION_ERROR": ProviderErrorCategory.VALIDATION_ERROR,
}


def category_for_code(code: str | None) -> ProviderErrorCategory:
    """Map an adapter error code to the standardized provider error category."""
    if not code:
        return ProviderErrorCategory.UNKNOWN
    direct = _ADAPTER_CODE_CATEGORIES.get(code)
    if direct is not None:
        return direct
    return classify_provider_error(code)


def category_for_exception(exc: BaseException) -> ProviderErrorCategory:
    """Classify any communication exception into a standardized category."""
    code = getattr(exc, "code", None)
    if code:
        return category_for_code(str(code))
    if isinstance(exc, TimeoutError):
        return ProviderErrorCategory.TIMEOUT
    if isinstance(exc, ConnectionError):
        return ProviderErrorCategory.NETWORK_ERROR
    return classify_provider_error(None, str(exc))


def failover_eligible(category: ProviderErrorCategory) -> bool:
    """Only infrastructure-level degradation justifies failing over to another provider."""
    return category in {
        ProviderErrorCategory.TIMEOUT,
        ProviderErrorCategory.NETWORK_ERROR,
        ProviderErrorCategory.PROVIDER_UNAVAILABLE,
        ProviderErrorCategory.RATE_LIMITED,
    }
