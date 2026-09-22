"""
Localization and formatting utilities for PesaGuard.

Provides East Africa Time (EAT) datetime formatting, Kenyan Shilling (KES) currency
formatting, locale normalization, and nested key translation fallbacks.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

_MISSING = object()
_EAT = ZoneInfo("Africa/Nairobi")


def _resolve_path(locale_data: Dict[str, Any], key: str, *, allow_camel_case: bool = False) -> Any:
    """Traverse nested dictionary structures using dotted key paths."""
    current: Any = locale_data
    parts = key.split(".")

    for index, part in enumerate(parts):
        if not isinstance(current, dict):
            return _MISSING

        if part in current:
            current = current[part]
            continue

        if allow_camel_case and index < len(parts) - 1:
            combined = part + "".join(segment[:1].upper() + segment[1:] for segment in parts[index + 1 :])
            if combined in current:
                return current[combined]

        return _MISSING

    return current


def resolve_translation(
    locale_data: Dict[str, Any],
    key: str,
    fallback_locale: Optional[Dict[str, Any]] = None,
) -> Any:
    """Resolve a nested translation key, falling back to English or the raw key string when missing."""
    if not locale_data or not isinstance(locale_data, dict):
        if fallback_locale and isinstance(fallback_locale, dict):
            fallback_val = _resolve_path(fallback_locale, key, allow_camel_case=True)
            return fallback_val if fallback_val is not _MISSING else key
        return key

    value = _resolve_path(locale_data, key)
    if value is not _MISSING:
        return value

    if fallback_locale is None or fallback_locale is locale_data:
        return key

    fallback_value = _resolve_path(fallback_locale, key, allow_camel_case=True)
    if fallback_value is not _MISSING:
        return fallback_value

    return key


def normalise_locale(locale: Optional[str]) -> str:
    """Normalize locale strings into standard ISO 639-1 language codes ('en' or 'sw')."""
    if not locale:
        return "en"
    value = str(locale).strip().lower()
    return "sw" if value.startswith("sw") else "en"


def format_ke_currency(amount: Any) -> str:
    """Format numeric values into standard Kenyan Shilling currency format (e.g. 'KES 1,250.00')."""
    if amount is None or amount == "":
        return "KES 0.00"

    try:
        if isinstance(amount, float):
            value = Decimal(str(amount))
        else:
            value = Decimal(amount)
    except (ArithmeticError, TypeError, ValueError, InvalidOperation):
        return str(amount)

    return f"KES {value:,.2f}"


def format_ke_datetime(value: Any) -> str:
    """Format naive or timezone-aware ISO datetimes into EAT (East Africa Time) strings."""
    if not value:
        return ""

    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        if not text:
            return ""
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            return text

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))

    local_dt = dt.astimezone(_EAT)
    return local_dt.strftime("%d %b %Y, %H:%M EAT")
