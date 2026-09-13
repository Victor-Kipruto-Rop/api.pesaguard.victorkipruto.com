"""
SQLAlchemy ORM Data Models for PesaGuard's Postgres Store.

Defines schemas for Daraja transactions, idempotency tracking, discrepancy logging,
webhooks, escalation rules, on-call schedules, email audits, and dead-letter queues.
"""

from __future__ import annotations

from datetime import datetime, timezone
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Transaction(Base):
    """Raw M-Pesa transaction events received from Daraja webhooks."""

    __tablename__ = "transactions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "provider_account_id", "trans_id", name="uq_transaction_scope_trans_id"),
        Index("ix_transaction_scope_trans_id", "tenant_id", "provider_account_id", "trans_id"),
        Index("ix_transaction_trans_id", "trans_id"),
        Index("ix_transaction_created_at", "created_at"),
        Index("ix_transaction_msisdn", "msisdn"),
    )

    id = Column(String, primary_key=True, default=lambda: f"txn_{uuid.uuid4().hex}")
    trans_id = Column(String, nullable=False)
    tenant_id = Column(String, nullable=False, default="default", server_default="default")
    provider_account_id = Column(String, nullable=False, default="legacy-default", server_default="legacy-default")
    trans_amount = Column(Numeric(18, 2), nullable=False)
    msisdn = Column(String, nullable=False)
    business_short_code = Column(String, nullable=False)
    trans_time = Column(String, nullable=False)  # Raw string timestamp format from Daraja
    raw_payload = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class ProcessedTransaction(Base):
    """
    Explicit Idempotency Ledger: Tracks which webhook callbacks have been received.
    
    Prevents race conditions and duplicate transaction handling using a unique constraint
    on daraja_trans_id.
    """

    __tablename__ = "processed_transactions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "provider_account_id", "daraja_trans_id", name="uq_processed_scope_trans_id"),
        Index("ix_processed_daraja_id", "daraja_trans_id"),
        Index("ix_processed_scope", "tenant_id", "provider_account_id"),
        Index("ix_processed_received_at", "received_at"),
    )

    id = Column(String, primary_key=True)
    daraja_trans_id = Column(String, nullable=False)
    tenant_id = Column(String, nullable=False, default="default", server_default="default")
    provider_account_id = Column(String, nullable=False, default="legacy-default", server_default="legacy-default")
    status = Column(String, nullable=False, default="received")  # received, validated, stored, failed
    processing_time_ms = Column(Integer, nullable=True)
    received_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    webhook_attempt_number = Column(Integer, default=1)
    source_ip = Column(String, nullable=True)
    signature_verified = Column(Boolean, default=False)
    error_reason = Column(String, nullable=True)
    reconciliation_status = Column(String, nullable=False, default="pending", server_default="pending")
    reconciliation_attempts = Column(Integer, nullable=False, default=0, server_default="0")
    reconciliation_started_at = Column(DateTime(timezone=True), nullable=True)
    reconciliation_completed_at = Column(DateTime(timezone=True), nullable=True)
    reconciliation_error = Column(Text, nullable=True)


class TransactionOutbox(Base):
    """Durable downstream publication intent for an accepted transaction."""

    __tablename__ = "transaction_outbox"
    __table_args__ = (
        UniqueConstraint("tenant_id", "event_key", name="uq_transaction_outbox_tenant_event"),
        Index("ix_transaction_outbox_pending", "status", "available_at", "created_at"),
        Index("ix_transaction_outbox_tenant_created", "tenant_id", "created_at"),
    )

    id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False, default="default", server_default="default")
    event_key = Column(String, nullable=False)
    topic = Column(String, nullable=False)
    payload = Column(JSON, nullable=False)
    status = Column(String, nullable=False, default="pending", server_default="pending")
    attempts = Column(Integer, nullable=False, default=0, server_default="0")
    available_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    locked_until = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    published_at = Column(DateTime(timezone=True), nullable=True)


class ReconciliationOutbox(Base):
    """Durable publication intent for matched/discrepancy outcomes."""

    __tablename__ = "reconciliation_outbox"
    __table_args__ = (
        UniqueConstraint("tenant_id", "event_key", name="uq_reconciliation_outbox_tenant_event"),
        Index("ix_reconciliation_outbox_pending", "status", "available_at", "created_at"),
    )

    id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False, default="default", server_default="default")
    event_key = Column(String, nullable=False)
    topic = Column(String, nullable=False)
    payload = Column(JSON, nullable=False)
    status = Column(String, nullable=False, default="pending", server_default="pending")
    attempts = Column(Integer, nullable=False, default=0, server_default="0")
    available_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    locked_until = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    published_at = Column(DateTime(timezone=True), nullable=True)


class Discrepancy(Base):
    """Reconciliation anomaly records flagged during transaction checks."""

    __tablename__ = "discrepancies"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_discrepancy_tenant_id"),
        Index("ix_discrepancy_trans_id", "trans_id"),
        Index("ix_discrepancy_tenant_id", "tenant_id"),
        Index("ix_discrepancy_detected_at", "detected_at"),
        Index("ix_discrepancy_status_resolved", "status", "resolved"),
    )

    id = Column(String, primary_key=True)  # Format: f"{trans_id}-{anomaly_type}"
    trans_id = Column(String, nullable=False)
    tenant_id = Column(String, nullable=False, default="default", server_default="default")
    anomaly_type = Column(String, nullable=False)
    status = Column(String, nullable=False, default="needs_review")
    severity = Column(String, nullable=False, default="warning")
    details = Column(Text, nullable=True)
    resolved = Column(Boolean, default=False)
    detected_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolution_note = Column(Text, nullable=True)
    latency_seconds = Column(Integer, nullable=True)
    assignee = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    timeline = Column(JSON, nullable=True, default=list)


class InternalRecord(Base):
    """Customer internal ledger or order system record baseline for comparison."""

    __tablename__ = "internal_records"
    __table_args__ = (
        Index("ix_internal_records_tenant_phone", "tenant_id", "phone_number"),
        Index("ix_internal_records_phone", "phone_number"),
        Index("ix_internal_records_synced", "synced_at"),
    )

    internal_ref = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False, default="default", server_default="default")
    amount = Column(Numeric(18, 2), nullable=False)
    phone_number = Column(String, nullable=False)
    status = Column(String, nullable=False)
    synced_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class WebhookConfig(Base):
    """Registered customer outbound webhook endpoint configurations."""

    __tablename__ = "webhook_configs"
    __table_args__ = (
        Index("ix_webhook_configs_tenant", "tenant_id"),
    )

    id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False)
    url = Column(String, nullable=False)
    event_types = Column(JSON, nullable=False)  # e.g., ["escalation", "resolution"]
    active = Column(Boolean, default=True)
    retry_attempts = Column(Integer, default=3)
    timeout_seconds = Column(Integer, default=10)
    signing_secret = Column(String, nullable=True)  # Dynamic HMAC signing key
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class WebhookDelivery(Base):
    """Outbound webhook delivery execution and response audit logs."""

    __tablename__ = "webhook_deliveries"
    __table_args__ = (
        Index("ix_webhook_deliveries_webhook_id", "webhook_id"),
        Index("ix_webhook_deliveries_created_at", "created_at"),
    )

    id = Column(String, primary_key=True)
    webhook_id = Column(String, nullable=False)
    event_type = Column(String, nullable=False)
    payload = Column(JSON, nullable=False)
    status = Column(String, nullable=False)  # success, failed, pending
    response_status = Column(Integer, nullable=True)
    response_body = Column(Text, nullable=True)
    attempt_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    delivered_at = Column(DateTime(timezone=True), nullable=True)


class EscalationRule(Base):
    """Per-tenant automated escalation criteria and notification triggers."""

    __tablename__ = "escalation_rules"
    __table_args__ = (
        Index("ix_escalation_rules_tenant", "tenant_id", "priority"),
    )

    id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    condition_field = Column(String, nullable=False)  # e.g., "severity", "anomaly_type"
    condition_operator = Column(String, nullable=False)  # e.g., "equals", "greater_than"
    condition_value = Column(String, nullable=False)
    action = Column(String, nullable=False)  # "escalate", "notify", "webhook"
    target = Column(String, nullable=True)
    webhook_url = Column(String, nullable=True)
    active = Column(Boolean, default=True)
    priority = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class OnCallRotation(Base):
    """On-call operational shift rotation schedules."""

    __tablename__ = "on_call_rotations"
    __table_args__ = (
        Index("ix_on_call_tenant_shift", "tenant_id", "shift_start", "shift_end"),
    )

    id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False)
    operator_id = Column(String, nullable=False)
    operator_name = Column(String, nullable=True)
    operator_email = Column(String, nullable=True)
    operator_phone = Column(String, nullable=True)
    shift_start = Column(DateTime(timezone=True), nullable=False)
    shift_end = Column(DateTime(timezone=True), nullable=False)
    is_active = Column(Boolean, default=False)
    escalation_level = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class EmailNotification(Base):
    """Audit log for outgoing email alerts and reconciliation reports."""

    __tablename__ = "email_notifications"
    __table_args__ = (
        Index("ix_email_tenant_created", "tenant_id", "created_at"),
    )

    id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False)
    recipient_email = Column(String, nullable=False)
    report_type = Column(String, nullable=False)  # "reconciliation", "daily_summary", "escalation"
    subject = Column(String, nullable=False)
    status = Column(String, nullable=False)  # "pending", "sent", "failed"
    content_hash = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class DeadLetter(Base):
    """Failed, malformed, or unprocessable webhook payload repository."""

    __tablename__ = "dead_letters"
    __table_args__ = (
        Index("ix_dead_letters_tenant", "tenant_id"),
        Index("ix_dead_letters_created", "created_at"),
    )

    id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=True, default="default")
    reason = Column(String, nullable=False)
    payload = Column(JSON, nullable=True)
    error_detail = Column(Text, nullable=True)
    attempts = Column(Integer, default=0)
    processed = Column(Boolean, default=False)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    replay_status = Column(String, nullable=False, default="idle", server_default="idle")
    replayed_by = Column(String, nullable=True)
    replayed_at = Column(DateTime(timezone=True), nullable=True)
    replay_reason = Column(Text, nullable=True)
    provider_account_id = Column(String, nullable=True)
    event_key = Column(String, nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    received_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class Report(Base):
    """Persisted daily, weekly, or ad-hoc reconciliation reports."""

    __tablename__ = "reports"
    __table_args__ = (
        Index("ix_reports_tenant_type", "tenant_id", "report_type"),
        Index("ix_reports_created", "created_at"),
    )

    id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False)
    report_type = Column(String, nullable=False)  # "daily", "weekly", "monthly"
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)
    content = Column(JSON, nullable=True)
    status = Column(String, nullable=False, default="generated")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    delivered_at = Column(DateTime(timezone=True), nullable=True)


class UserAccount(Base):
    """Local account record provisioned from an external IdP or internal directory."""

    __tablename__ = "user_accounts"

    id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False, default="default")
    username = Column(String, nullable=False)
    email = Column(String, nullable=True)
    password_hash = Column(String, nullable=True)
    password_salt = Column(String, nullable=True)
    roles = Column(JSON, nullable=False, default=list)
    permissions = Column(JSON, nullable=False, default=list)
    attributes = Column(JSON, nullable=True, default=dict)
    mfa_enabled = Column(Boolean, nullable=False, default=False)
    status = Column(String, nullable=False, default="active")
    authorization_version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)


class Organization(Base):
    """Top-level SaaS organization or customer tenant container."""

    __tablename__ = "organizations"
    __table_args__ = (
        Index("ix_organizations_tenant_slug", "tenant_id", "slug", unique=True),
        Index("ix_organizations_tenant_id", "tenant_id"),
    )

    id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False, default="default")
    name = Column(String, nullable=False)
    slug = Column(String, nullable=False)
    owner_user_id = Column(String, nullable=True)
    status = Column(String, nullable=False, default="active")
    settings = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)


class Team(Base):
    """Functional team within an organization."""

    __tablename__ = "teams"
    __table_args__ = (
        Index("ix_teams_organization_tenant", "organization_id", "tenant_id"),
        Index("ix_teams_slug", "tenant_id", "slug", unique=False),
    )

    id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False, default="default")
    organization_id = Column(String, nullable=False)
    name = Column(String, nullable=False)
    slug = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class Department(Base):
    """Department or sub-unit under a team or organization."""

    __tablename__ = "departments"
    __table_args__ = (
        Index("ix_departments_organization_tenant", "organization_id", "tenant_id"),
        Index("ix_departments_team", "team_id"),
    )

    id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False, default="default")
    organization_id = Column(String, nullable=False)
    team_id = Column(String, nullable=True)
    name = Column(String, nullable=False)
    slug = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class OrganizationMembership(Base):
    """Associates users with organizations, teams, and departments."""

    __tablename__ = "organization_memberships"
    __table_args__ = (
        Index("ix_org_membership_user_tenant", "tenant_id", "user_id"),
        Index("ix_org_membership_org", "organization_id"),
    )

    id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False, default="default")
    user_id = Column(String, nullable=False)
    organization_id = Column(String, nullable=False)
    team_id = Column(String, nullable=True)
    department_id = Column(String, nullable=True)
    role = Column(String, nullable=False, default="member")
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class OrganizationApproval(Base):
    """Approval workflow records for SaaS org onboarding and lifecycle changes."""

    __tablename__ = "organization_approvals"
    __table_args__ = (
        Index("ix_org_approval_tenant", "tenant_id", "status"),
    )

    id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False, default="default")
    organization_id = Column(String, nullable=True)
    request_type = Column(String, nullable=False, default="create")
    requested_by = Column(String, nullable=False)
    approver_id = Column(String, nullable=True)
    status = Column(String, nullable=False, default="pending")
    reason = Column(Text, nullable=True)
    approval_metadata = Column(JSON, nullable=True, default=dict)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)


class TenantConfiguration(Base):
    """Tenant-wide configuration and feature flags."""

    __tablename__ = "tenant_configurations"
    __table_args__ = (
        Index("ix_tenant_config_unique", "tenant_id", unique=True),
    )

    id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False, default="default")
    organization_id = Column(String, nullable=True)
    config = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)


class TenantLimit(Base):
    """Enforced limit for a tenant or organization metric."""

    __tablename__ = "tenant_limits"
    __table_args__ = (
        Index("ix_tenant_limits_tenant_metric", "tenant_id", "organization_id", "metric_name", "period", unique=True),
    )

    id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False, default="default")
    organization_id = Column(String, nullable=False)
    metric_name = Column(String, nullable=False)
    limit_value = Column(Float, nullable=False, default=0.0)
    period = Column(String, nullable=False, default="monthly")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class TenantUsage(Base):
    """Usage tracking for tenant and organization resource consumption."""

    __tablename__ = "tenant_usage"
    __table_args__ = (
        Index("ix_tenant_usage_tenant_metric", "tenant_id", "organization_id", "metric_name", "period", unique=True),
    )

    id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False, default="default")
    organization_id = Column(String, nullable=False)
    metric_name = Column(String, nullable=False)
    current_usage = Column(Float, nullable=False, default=0.0)
    period = Column(String, nullable=False, default="monthly")
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)


class UserSession(Base):
    """Authenticated session record for device and session risk evaluation."""

    __tablename__ = "user_sessions"

    id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False, default="default")
    user_id = Column(String, nullable=True)
    device_id = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    ip_address = Column(String, nullable=True)
    active = Column(Boolean, nullable=False, default=True)
    issued_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    session_metadata = Column(JSON, nullable=True, default=dict)


class OIDCProvider(Base):
    """Tenant-managed external OIDC identity provider configuration."""

    __tablename__ = "oidc_providers"

    id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False, default="default")
    provider_name = Column(String, nullable=False)
    issuer = Column(String, nullable=False)
    client_id = Column(String, nullable=True)
    client_secret = Column(String, nullable=True)
    authorization_endpoint = Column(String, nullable=True)
    token_endpoint = Column(String, nullable=True)
    userinfo_endpoint = Column(String, nullable=True)
    jwks_uri = Column(String, nullable=True)
    scopes = Column(JSON, nullable=False, default=list)
    allowed_roles = Column(JSON, nullable=False, default=list)
    auto_provision = Column(Boolean, nullable=False, default=False)
    claim_mapping = Column(JSON, nullable=True, default=dict)
    provider_metadata = Column("provider_metadata", JSON, nullable=True, default=dict)
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)


class PaymentProvider(Base):
    """Tenant-scoped payment provider registration and operational configuration."""

    __tablename__ = "payment_providers"

    id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False, default="default", index=True)
    name = Column(String, nullable=False)
    provider_type = Column(String, nullable=False, default="payment")
    status = Column(String, nullable=False, default="active")
    credentials = Column(JSON, nullable=False, default=dict)
    api_configuration = Column(JSON, nullable=False, default=dict)
    account_configuration = Column(JSON, nullable=False, default=dict)
    provider_metadata = Column("metadata", JSON, nullable=False, default=dict)
    supported_currencies = Column(JSON, nullable=False, default=list)
    capabilities = Column(JSON, nullable=False, default=list)
    webhook_configuration = Column(JSON, nullable=False, default=dict)
    connection_status = Column(String, nullable=False, default="unknown")
    connection_checked_at = Column(DateTime(timezone=True), nullable=True)
    health_status = Column(String, nullable=False, default="unknown")
    health_details = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)


class ApiKeyRecord(Base):
    """Tenant-scoped API keys issued for machine access."""

    __tablename__ = "api_key_records"

    id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False, default="default")
    key_hash = Column(String(128), nullable=False, unique=True, index=True)
    key_prefix = Column(String(32), nullable=False)
    role = Column(String, nullable=False, default="read-only")
    scopes = Column(JSON, nullable=False, default=list, server_default="[]")
    expires_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    rotated_from_id = Column(String, nullable=True)
    api_metadata = Column("api_metadata", JSON, nullable=True, default=dict)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class MFAChallenge(Base):
    """MFA challenge state for end-user verification flows."""

    __tablename__ = "mfa_challenges"

    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False)
    tenant_id = Column(String, nullable=False)
    code_hash = Column(String(128), nullable=False)
    status = Column(String, nullable=False, default="pending")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    attempts = Column(Integer, nullable=False, default=0)


class PasswordlessChallenge(Base):
    """Passwordless challenge state for email or magic-link verification."""

    __tablename__ = "passwordless_challenges"

    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False)
    tenant_id = Column(String, nullable=False)
    token_hash = Column(String(128), nullable=False)
    status = Column(String, nullable=False, default="pending")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    attempts = Column(Integer, nullable=False, default=0)
