import json

import pytest

from retention_policy import RetentionPolicyError, load_retention_policy


def test_configured_retention_policy_covers_required_categories():
    policy = load_retention_policy()
    assert {
        "transactions",
        "audit",
        "application_logs",
        "security_logs",
        "raw_provider_data",
        "analytics",
        "user_data",
    } <= set(policy.rules)
    assert policy.rule("transactions").storage.startswith("PostgreSQL")
    assert policy.rule("raw_provider_data").deletion_method


def test_retention_policy_rejects_incomplete_rules(tmp_path):
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps({"categories": {"transactions": {"owner": "Finance"}}}), encoding="utf-8")
    with pytest.raises(RetentionPolicyError):
        load_retention_policy(str(path))