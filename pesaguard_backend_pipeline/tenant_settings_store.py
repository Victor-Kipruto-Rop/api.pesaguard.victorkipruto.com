"""Compatibility shim for the legacy top-level tenant_settings_store module."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from typing import Any, Dict, Iterable, List, Optional


class TenantSettingsStore:
    """Thread-safe JSON-backed tenant settings store with locale and residency helpers."""

    def __init__(self, path: Optional[str] = None):
        self.path = path or os.getenv("TENANT_SETTINGS_FILE", "tenant_settings.json")
        self._data: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                payload = json.load(fh)
            if isinstance(payload, dict):
                self._data = {str(k): (v if isinstance(v, dict) else {}) for k, v in payload.items()}
        except FileNotFoundError:
            self._data = {}
        except json.JSONDecodeError:
            self._data = {}

    def _save(self) -> None:
        directory = os.path.dirname(self.path) or "."
        os.makedirs(directory, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(self._data, fh, indent=2, sort_keys=True)

    def get(self, tenant_id: str, default: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        tenant_key = str(tenant_id or "default")
        value = self._data.get(tenant_key, {})
        if not isinstance(value, dict):
            value = {}
        if default is not None:
            merged = deepcopy(default)
            merged.update(value)
            return merged
        return deepcopy(value)

    def update(self, tenant_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(patch, dict):
            raise ValueError("Tenant settings update requires a dictionary payload.")
        tenant_key = str(tenant_id or "default")
        existing = self.get(tenant_key)
        merged = deepcopy(existing)
        for key, value in patch.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = {**merged[key], **value}
            else:
                merged[key] = value
        if "preferred_locale" in merged and merged["preferred_locale"]:
            merged["preferred_locale"] = str(merged["preferred_locale"]).strip().lower()
            if "-" in merged["preferred_locale"]:
                locale_root = merged["preferred_locale"].split("-", 1)[0]
                if locale_root in {"en", "sw"}:
                    merged["preferred_locale"] = locale_root
        self._data[tenant_key] = merged
        self._save()
        return deepcopy(merged)

    def resolve_locale(self, tenant_id: str, user_id: Optional[str] = None, fallback_locale: str = "en") -> str:
        tenant_cfg = self.get(str(tenant_id or "default"), {})
        if user_id and isinstance(tenant_cfg.get("user_locale_overrides"), dict):
            override = tenant_cfg["user_locale_overrides"].get(str(user_id))
            if override:
                return str(override).lower().split("-", 1)[0]
        preferred = tenant_cfg.get("preferred_locale") or tenant_cfg.get("locale")
        if preferred:
            return str(preferred).lower().split("-", 1)[0]
        fallback = self.get("default", {}).get("preferred_locale") or fallback_locale
        return str(fallback).lower().split("-", 1)[0]

    def get_residency_context(self, tenant_id: str) -> Dict[str, Any]:
        tenant_cfg = self.get(str(tenant_id or "default"), {})
        return {
            "tenant_id": str(tenant_id or "default"),
            "deployment_region": tenant_cfg.get("deployment_region") or tenant_cfg.get("region") or "default",
            "data_residency": tenant_cfg.get("data_residency") or "local",
            "preferred_locale": tenant_cfg.get("preferred_locale") or tenant_cfg.get("locale") or "en",
        }

    def list_tenant_ids(self) -> List[str]:
        return sorted(str(key) for key in self._data.keys())

    def get_all_tenants(self) -> Dict[str, Dict[str, Any]]:
        return deepcopy(self._data)

