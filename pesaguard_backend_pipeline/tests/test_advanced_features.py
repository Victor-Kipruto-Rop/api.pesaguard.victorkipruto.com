"""Test suite for advanced features: webhooks, auth, email, escalations, on-call, search, rate limiting."""

import os
import pytest
import json
from datetime import datetime, timezone, timedelta

from test_config import configure_test_database

configure_test_database()

from app_4_advanced_features import app, SessionLocal
from models import Base, Discrepancy, EscalationRule, OnCallRotation, WebhookConfig, UserAccount
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from auth_rbac import AuthRBAC


@pytest.fixture
def client():
    """Create test client."""
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def token_accounts():
    """Persist isolated principals required by the real account-state verifier."""
    accounts = [
        UserAccount(id="user_admin", username="admin", tenant_id="test-tenant", roles=["admin"], status="active", authorization_version=1),
        UserAccount(id="user_operator", username="operator1", tenant_id="test-tenant", roles=["operator"], status="active", authorization_version=1),
    ]
    with SessionLocal() as session:
        session.add_all(accounts)
        session.commit()
    try:
        yield
    finally:
        with SessionLocal() as session:
            session.query(UserAccount).filter(
                UserAccount.id.in_(["user_admin", "user_operator"]),
                UserAccount.tenant_id == "test-tenant",
            ).delete(synchronize_session=False)
            session.commit()


@pytest.fixture
def admin_token(token_accounts):
    """Generate admin JWT token."""
    return AuthRBAC.generate_token(
        user_id="user_admin",
        username="admin",
        tenant_id="test-tenant",
        roles=["admin"],
    )


@pytest.fixture
def operator_token(token_accounts):
    """Generate operator JWT token."""
    return AuthRBAC.generate_token(
        user_id="user_operator",
        username="operator1",
        tenant_id="test-tenant",
        roles=["operator"],
    )


class TestAuthentication:
    """Test authentication and RBAC."""

    def test_login(self, client):
        """Test user login."""
        response = client.post("/auth/login", json={
            "username": "testuser",
            "password": "password",
            "tenant_id": "test-tenant",
        })
        assert response.status_code == 200
        data = response.get_json()
        assert "token" in data
        assert data["username"] == "testuser"

    def test_verify_token_valid(self, client, admin_token):
        """Test token verification with valid token."""
        response = client.get(
            "/auth/verify",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["username"] == "admin"

    @pytest.mark.parametrize("change", ["missing", "disabled", "stale", "wrong-tenant"])
    def test_verify_token_rejects_invalid_account_state(self, client, admin_token, change):
        with SessionLocal() as session:
            account = session.get(UserAccount, "user_admin")
            if change == "missing":
                session.delete(account)
            elif change == "disabled":
                account.status = "disabled"
            elif change == "stale":
                account.authorization_version += 1
            else:
                account.tenant_id = "other-tenant"
            session.commit()
        try:
            response = client.get("/auth/verify", headers={"Authorization": f"Bearer {admin_token}"})
            assert response.status_code == 401
        finally:
            if change == "wrong-tenant":
                with SessionLocal() as session:
                    session.get(UserAccount, "user_admin").tenant_id = "test-tenant"
                    session.commit()

    def test_verify_token_missing(self, client):
        """Test token verification without token."""
        response = client.get("/auth/verify")
        assert response.status_code == 401

    def test_protected_endpoint_requires_permission(self, client, operator_token):
        """Test operator cannot access admin endpoints."""
        response = client.get(
            "/webhooks?tenant_id=test-tenant",
            headers={"Authorization": f"Bearer {operator_token}"},
        )
        # Operator doesn't have manage:webhooks permission
        assert response.status_code in [403, 404]


class TestWebhooks:
    """Test webhook functionality."""

    def test_create_webhook(self, client, admin_token):
        """Test webhook creation."""
        response = client.post(
            "/webhooks",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "tenant_id": "test-tenant",
                "url": "https://example.com/webhooks",
                "event_types": ["escalation", "resolution"],
                "retry_attempts": 3,
                "timeout_seconds": 10,
            },
        )
        assert response.status_code == 201
        data = response.get_json()
        assert "id" in data
        assert data["url"] == "https://example.com/webhooks"

    def test_list_webhooks(self, client, admin_token):
        """Test listing webhooks."""
        # First create a webhook
        client.post(
            "/webhooks",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "tenant_id": "test-tenant",
                "url": "https://example.com/hook1",
                "event_types": ["escalation"],
            },
        )

        # Then list
        response = client.get(
            "/webhooks?tenant_id=test-tenant",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.get_json()
        assert "webhooks" in data


class TestEscalationRules:
    """Test escalation rules."""

    def test_create_escalation_rule(self, client, admin_token):
        """Test creating an escalation rule."""
        response = client.post(
            "/escalation-rules",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "tenant_id": "test-tenant",
                "name": "Critical Severity Escalation",
                "description": "Escalate critical severity incidents",
                "condition_field": "severity",
                "condition_operator": "equals",
                "condition_value": "critical",
                "action": "escalate",
                "target": "senior_operator",
                "priority": 1,
            },
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data["name"] == "Critical Severity Escalation"

    def test_list_escalation_rules(self, client, admin_token):
        """Test listing escalation rules."""
        # Create a rule
        client.post(
            "/escalation-rules",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "tenant_id": "test-tenant",
                "name": "Test Rule",
                "condition_field": "severity",
                "condition_operator": "equals",
                "condition_value": "critical",
                "action": "escalate",
            },
        )

        # List rules
        response = client.get(
            "/escalation-rules?tenant_id=test-tenant",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.get_json()
        assert "rules" in data


class TestOnCallRotations:
    """Test on-call rotation tracking."""

    def test_create_on_call_rotation(self, client, admin_token):
        """Test creating an on-call rotation."""
        now = datetime.now(timezone.utc)
        shift_start = now.isoformat()
        shift_end = (now + timedelta(hours=8)).isoformat()

        response = client.post(
            "/on-call/rotations",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "tenant_id": "test-tenant",
                "operator_id": "op_001",
                "operator_name": "John Operator",
                "operator_email": "john@example.com",
                "operator_phone": "+254712345678",
                "shift_start": shift_start,
                "shift_end": shift_end,
                "escalation_level": 1,
            },
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data["operator_id"] == "op_001"

    def test_get_active_on_call(self, client, admin_token):
        """Test getting active on-call operators."""
        now = datetime.now(timezone.utc)
        
        # Create active rotation
        client.post(
            "/on-call/rotations",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "tenant_id": "test-tenant",
                "operator_id": "op_001",
                "operator_name": "Active Operator",
                "operator_email": "active@example.com",
                "operator_phone": "+254712345678",
                "shift_start": now.isoformat(),
                "shift_end": (now + timedelta(hours=8)).isoformat(),
                "escalation_level": 1,
            },
        )

        # Get active
        response = client.get(
            "/on-call/rotations/active?tenant_id=test-tenant",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.get_json()
        assert "coverage" in data
        assert "active_rotations" in data

    def test_bulk_create_on_call(self, client, admin_token):
        """Test bulk creating on-call rotations."""
        now = datetime.now(timezone.utc)
        rotations_data = [
            {
                "operator_id": "op_001",
                "operator_name": "Operator 1",
                "operator_email": "op1@example.com",
                "operator_phone": "+254712345678",
                "shift_start": now.isoformat(),
                "shift_end": (now + timedelta(hours=8)).isoformat(),
                "escalation_level": 1,
            },
            {
                "operator_id": "op_002",
                "operator_name": "Operator 2",
                "operator_email": "op2@example.com",
                "operator_phone": "+254712345679",
                "shift_start": (now + timedelta(hours=8)).isoformat(),
                "shift_end": (now + timedelta(hours=16)).isoformat(),
                "escalation_level": 1,
            },
        ]

        response = client.post(
            "/on-call/bulk",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "tenant_id": "test-tenant",
                "rotations": rotations_data,
            },
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data["created"] == 2


class TestEmailNotifications:
    """Test email notification endpoints."""

    def test_send_reconciliation_email(self, client, operator_token):
        """Test sending reconciliation report email."""
        response = client.post(
            "/emails/reconciliation",
            headers={"Authorization": f"Bearer {operator_token}"},
            json={
                "tenant_id": "test-tenant",
                "recipient_email": "manager@example.com",
                "report_data": {
                    "total_discrepancies": 42,
                    "resolved": 38,
                    "pending": 4,
                    "sla_compliance": 95,
                    "avg_resolution_time": 15,
                },
            },
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] in ["sent", "pending", "failed"]

    def test_send_escalation_email(self, client, operator_token):
        """Test sending escalation notification."""
        response = client.post(
            "/emails/escalation",
            headers={"Authorization": f"Bearer {operator_token}"},
            json={
                "tenant_id": "test-tenant",
                "recipient_email": "senior@example.com",
                "incident_data": {
                    "anomaly_type": "double_charge",
                    "severity": "critical",
                    "amount": 5000,
                    "trans_id": "TX123456",
                    "detected_at": datetime.now(timezone.utc).isoformat(),
                },
            },
        )
        assert response.status_code == 200
        data = response.get_json()
        assert "id" in data


class TestAdvancedSearch:
    """Test advanced search with boolean operators."""

    def test_search_with_query(self, client, operator_token):
        """Test search with boolean query."""
        response = client.get(
            "/search?tenant_id=test-tenant&q=severity:critical%20AND%20status:open",
            headers={"Authorization": f"Bearer {operator_token}"},
        )
        assert response.status_code == 200
        data = response.get_json()
        assert "results" in data
        assert "parsed" in data

    def test_structured_search(self, client, operator_token):
        """Test structured search with filters."""
        response = client.get(
            "/search/structured?tenant_id=test-tenant&severity=critical&status=open",
            headers={"Authorization": f"Bearer {operator_token}"},
        )
        assert response.status_code == 200
        data = response.get_json()
        assert "results" in data
        assert "filters" in data

    def test_get_search_filters(self, client, operator_token):
        """Test getting available search filters."""
        response = client.get(
            "/search/filters?tenant_id=test-tenant",
            headers={"Authorization": f"Bearer {operator_token}"},
        )
        assert response.status_code == 200
        data = response.get_json()
        assert "available_filters" in data


class TestRateLimiting:
    """Test rate limiting on bulk operations."""

    def test_bulk_assign_rate_limit(self, client, admin_token):
        """Test rate limiting on bulk assign."""
        # First request should succeed
        response1 = client.post(
            "/bulk/assign",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "tenant_id": "test-tenant",
                "incident_ids": ["inc_001", "inc_002"],
                "assignee": "operator1",
            },
        )
        assert response1.status_code == 200

        # Verify rate limit status
        data = response1.get_json()
        assert "rate_limit" in data

    def test_bulk_escalate_rate_limit(self, client, admin_token):
        """Test rate limiting on bulk escalate."""
        response = client.post(
            "/bulk/escalate",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "tenant_id": "test-tenant",
                "incident_ids": ["inc_001"],
            },
        )
        assert response.status_code == 200
        data = response.get_json()
        assert "rate_limit" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
