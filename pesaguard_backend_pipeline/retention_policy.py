"""Configurable data-retention policy registry."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping, Optional


class RetentionPolicyError(ValueError):
    """Raised when retention policy configuration is incomplete or invalid."""


@dataclass(frozen=True)
class DataRetentionRule:
    data_type: str
    owner: str
    purpose: str
    retention_days: int
    storage: str
    access_level: str
    deletion_method: str

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "DataRetentionRule":
        required = ("data_type", "owner", "purpose", "retention_days", "storage", "access_level", "deletion_method")
        missing = [key for key in required if not str(value.get(key) or "").strip()]
        if missing:
            raise RetentionPolicyError(f"retention rule is missing fields: {', '.join(missing)}")
        try:
            days = int(value["retention_days"])
        except (TypeError, ValueError) as exc:
            raise RetentionPolicyError("retention_days must be an integer") from exc
        if days <= 0:
            raise RetentionPolicyError("retention_days must be greater than zero")
        return cls(
            data_type=str(value["data_type"]),
            owner=str(value["owner"]),
            purpose=str(value["purpose"]),
            retention_days=days,
            storage=str(value["storage"]),
            access_level=str(value["access_level"]),
            deletion_method=str(value["deletion_method"]),
        )


class RetentionPolicy:
    def __init__(self, rules: Mapping[str, DataRetentionRule]):
        self.rules = dict(rules)
        if not self.rules:
            raise RetentionPolicyError("retention policy must contain at least one rule")

    def rule(self, category: str) -> DataRetentionRule:
        try:
            return self.rules[category]
        except KeyError as exc:
            raise RetentionPolicyError(f"no retention rule configured for {category!r}") from exc

    def retention_days(self, category: str) -> int:
        override = os.getenv(f"PESAGUARD_RETENTION_DAYS_{category.upper()}")
        return int(override) if override else self.rule(category).retention_days

    @classmethod
    def from_file(cls, path: str | Path) -> "RetentionPolicy":
        try:
            document = json.loads(Path(path).read_text(encoding="utf-8"))
            rules = {key: DataRetentionRule.from_dict(value) for key, value in document["categories"].items()}
        except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
            raise RetentionPolicyError(f"could not load retention policy: {path}") from exc
        return cls(rules)


def load_retention_policy(path: Optional[str] = None) -> RetentionPolicy:
    configured_path = path or os.getenv("PESAGUARD_RETENTION_POLICY_FILE")
    policy_path = Path(configured_path) if configured_path else Path(__file__).with_name("retention_policy.json")
    return RetentionPolicy.from_file(policy_path)