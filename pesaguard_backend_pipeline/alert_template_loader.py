"""Robust alert template loader and renderer for localized operational notifications."""

from __future__ import annotations

import logging
import re
import threading
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from localization_utils import normalise_locale

logger = logging.getLogger("pesaguard.templates")

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "alerting" / "templates"

DEFAULT_FIELDS_EN: Dict[str, str] = {
    "title": "PesaGuard discrepancy detected",
    "transaction": "Transaction",
    "severity": "Severity",
    "status": "Status",
    "issues": "Issues",
    "no_issues": "No additional details",
    "detected_at": "Detected at",
    "amount": "Amount",
}

DEFAULT_FIELDS_SW: Dict[str, str] = {
    "title": "PesaGuard imegundua tofauti",
    "transaction": "Muamala",
    "severity": "Ukali",
    "status": "Hali",
    "issues": "Mambo yaliyotokea",
    "no_issues": "Hakuna maandishi ya ziada",
    "detected_at": "Iligunduliwa saa",
    "amount": "Kiasi",
}

# Thread-safe file cache storing: (mtime, content_string)
_TEMPLATE_CACHE: Dict[str, Tuple[float, str]] = {}
_CACHE_LOCK = threading.Lock()


def _parse_frontmatter(content: str) -> Dict[str, str]:
    """Robustly parse YAML-style frontmatter headers from markdown strings."""
    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return {}

    fields: Dict[str, str] = {}
    for line in match.group(1).splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        # Strip surrounding quotes if present in frontmatter values
        cleaned_value = value.strip().strip('"').strip("'")
        fields[key.strip()] = cleaned_value
    return fields


def _template_body(content: str) -> str:
    """Extract markdown message body beneath frontmatter blocks."""
    return re.sub(r"^---\s*\n.*?\n---\s*\n?", "", content, count=1, flags=re.DOTALL).strip()


def _read_template_file(name: str) -> str:
    """Read template file safely from disk with an mtime-aware thread-safe cache."""
    path = TEMPLATES_DIR / name
    if not path.exists():
        logger.warning("Template file not found on disk: %s", path)
        return ""

    try:
        current_mtime = path.stat().st_mtime
    except OSError as e:
        logger.error("Failed to check template file stats for %s: %s", path, e)
        return ""

    with _CACHE_LOCK:
        cached = _TEMPLATE_CACHE.get(name)
        if cached and cached[0] == current_mtime:
            return cached[1]

    try:
        content = path.read_text(encoding="utf-8")
        with _CACHE_LOCK:
            _TEMPLATE_CACHE[name] = (current_mtime, content)
        return content
    except Exception as e:
        logger.error("Failed to read template file %s: %s", path, e)
        return ""


def load_alert_fields(locale: str) -> Dict[str, str]:
    """Load localized UI field dictionaries with graceful fallback to English/Swahili defaults."""
    locale_code = normalise_locale(locale)
    fallback = DEFAULT_FIELDS_EN if locale_code == "en" else DEFAULT_FIELDS_SW
    filename = f"alert_fields_{locale_code}.md"
    
    content = _read_template_file(filename)
    if not content:
        return dict(fallback)

    parsed = _parse_frontmatter(content)
    merged = dict(fallback)
    merged.update(parsed)
    return merged


def render_message_template(template_name: str, context: Dict[str, Any]) -> str:
    """Render notification templates safely replacing {{variable}} tokens with context data."""
    content = _read_template_file(template_name)
    if not content:
        return ""

    body = _template_body(content)
    if not body:
        return ""

    # Safe regex replacement for placeholders like {{variable_name}}
    def _replacer(match: re.Match) -> str:
        key = match.group(1).strip()
        val = context.get(key)
        return str(val) if val is not None else ""

    rendered = re.sub(r"\{\{([^}]+)\}\}", _replacer, body)
    return rendered.strip()
