"""
PesaGuard Engineering Roadmap & Business Readiness Track Definition.

Defines the 15-phase technical evolution and parallel business/compliance track
for PesaGuard's M-Pesa automated reconciliation engine.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional


@dataclass
class Phase:
    number: int
    title: str
    timeline: str
    source_prompt: str
    description: str
    bullets: List[str]

    def to_dict(self) -> Dict[str, Any]:
        """Convert Phase instance to a dictionary."""
        return asdict(self)


PHASES: List[Phase] = [
    Phase(
        number=0,
        title="Discovery & Validation",
        timeline="Week 1",
        source_prompt="Master Build Prompt",
        description="Validate pilot customers, Daraja sandbox access, and manual reconciliation pain before coding.",
        bullets=[
            "Identify candidate pilot customers",
            "Validate manual reconciliation pain",
            "Confirm Daraja sandbox access and callback payload samples",
            "Do not proceed without directional validation",
        ],
    ),
    Phase(
        number=1,
        title="Core Pipeline",
        timeline="Weeks 2-3",
        source_prompt="Master Build Prompt",
        description="Build the multi-tenant ingestion and storage foundation for Daraja callbacks and transaction reconciliation.",
        bullets=[
            "Webhook receiver validating Daraja callbacks",
            "Publish validated events to Kafka",
            "Tenant-scoped Postgres schema for transactions, discrepancies, audit logs",
            "Duplicate/invalid/large-amount detection",
            "Audit logging and local docker-compose setup",
        ],
    ),
    Phase(
        number=2,
        title="Real Matching & Reconciliation Logic",
        timeline="Weeks 4-5",
        source_prompt="Master Build Prompt",
        description="Implement connector-based matching against tenant internal records and partial-match reconciliation logic.",
        bullets=[
            "BaseConnector interface and per-tenant field mapping",
            "Phone+amount+time-window matching against internal records",
            "Need-review tier for partial matches",
            "Missing-callback detection and late-match auto-resolution",
            "ConnectorRegistry ensures tenant-agnostic reconciliation logic",
        ],
    ),
    Phase(
        number=3,
        title="Alerting System",
        timeline="Weeks 6-7",
        source_prompt="Master Build Prompt",
        description="Build a decoupled alerting service with multi-channel delivery and escalation support.",
        bullets=[
            "Dedicated alerting service consuming discrepancies topic",
            "Slack, SMS, and email delivery channels",
            "Severity tiers with distinct routing",
            "Escalation, acknowledgement, and daily digest",
            "Alert deduplication and delivery audit logging",
        ],
    ),
    Phase(
        number=4,
        title="Monitoring & Observability",
        timeline="Weeks 8-9",
        source_prompt="Master Build Prompt",
        description="Add health, metrics, structured logging, and runbook guidance for platform reliability.",
        bullets=[
            "/health and Prometheus-compatible /metrics endpoints",
            "Structured JSON logs correlated by tenant_id/trans_id",
            "Kafka lag, latency, and connector health metrics",
            "Separate ops-only alerting channel",
            "Runbook for common failure scenarios",
        ],
    ),
    Phase(
        number=5,
        title="Dashboards (Operational + Customer)",
        timeline="Weeks 10-12",
        source_prompt="Master Build Prompt",
        description="Ship internal Grafana metrics and a tenant-facing dashboard with reconciliation workflows.",
        bullets=[
            "Operational Grafana dashboard provisioned as code",
            "Customer-facing Next.js dashboard with discrepancy feed",
            "Discrepancy detail and resolution flow",
            "Tenant settings and scoped auth",
            "Every view/API call tenant-scoped",
        ],
    ),
    Phase(
        number=6,
        title="Security & API Protection",
        timeline="Week 13",
        source_prompt="Master Build Prompt",
        description="Harden the webhook receiver and dashboard API with rate limits, validation, and token protection.",
        bullets=[
            "Rate limiting and request size limits",
            "Daraja source validation",
            "Expiring/revocable dashboard auth tokens",
            "Tenant isolation at the database layer",
        ],
    ),
    Phase(
        number=7,
        title="Backup, DR & Data Retention",
        timeline="Week 14",
        source_prompt="Master Build Prompt",
        description="Implement backups, restores, and documented retention and tenant-offboarding procedures.",
        bullets=[
            "Automated Postgres backups with restore testing",
            "Kafka topic retention for replay",
            "Document retention periods and offboarding",
            "Audit log retention as a separate rule",
        ],
    ),
    Phase(
        number=8,
        title="Incident Response Tooling",
        timeline="Week 15",
        source_prompt="Master Build Prompt",
        description="Define on-call, incident severity, customer communication, and postmortem processes.",
        bullets=[
            "Concrete on-call/paging definition",
            "SEV1/SEV2/SEV3 definitions",
            "Customer notification and postmortem templates",
            "Single INCIDENT_RESPONSE.md",
        ],
    ),
    Phase(
        number=9,
        title="API Documentation",
        timeline="Week 15 (parallel)",
        source_prompt="Master Build Prompt",
        description="Publish an OpenAPI/Swagger spec and interactive docs for the dashboard API.",
        bullets=[
            "OpenAPI/Swagger spec for dashboard API",
            "Interactive docs endpoint",
            "Extend existing webhook payload documentation",
        ],
    ),
    Phase(
        number=10,
        title="Testing & Hardening",
        timeline="Weeks 16-17",
        source_prompt="Master Build Prompt",
        description="Build coverage for anomaly rules, integration flows, idempotency, load, and multi-tenant isolation.",
        bullets=[
            "Unit tests for anomaly and reconciliation rules",
            "Integration tests with realistic Daraja fixtures",
            "Idempotency, load, and isolation tests",
            "Escalation timing and channel separation verification",
        ],
    ),
    Phase(
        number=11,
        title="Deployment & Launch",
        timeline="Week 18+",
        source_prompt="Master Build Prompt",
        description="Prepare a production-ready deployment path with CI, secrets management, and HTTPS webhook delivery.",
        bullets=[
            "Single-VM docker-compose deployment",
            "GitHub Actions CI for test/build/deploy",
            "Environment-injected secrets only",
            "HTTPS webhook receiver and onboarding runbook",
        ],
    ),
    Phase(
        number=12,
        title="Operational Gaps",
        timeline="Weeks 19-20",
        source_prompt="Gaps Addendum",
        description="Fill in remaining operational capabilities like OAuth, staging, scanning, RBAC, exports, versioning, and rotation.",
        bullets=[
            "Daraja OAuth token management",
            "Staging environment isolated from production",
            "Dependency scanning in CI",
            "RBAC with action audit logging",
            "Async tenant-scoped CSV export",
            "API versioning and deprecation policy",
            "Secrets rotation documentation",
        ],
    ),
    Phase(
        number=13,
        title="Tenant Lifecycle, Threat Model, Feature Flags, Billing, Help Docs",
        timeline="Weeks 21-23",
        source_prompt="Tenant/Threat/Billing Addendum",
        description="Add tenant lifecycle workflows, a reconciliation threat model, feature flags, usage tracking, and billing/help docs.",
        bullets=[
            "Tenant provisioning with shadow mode default",
            "Threat model for spoofing/replay/compromised connectors",
            "Per-tenant feature flags and rule versioning",
            "Usage tracking and billing integration readiness",
            "Getting started guide and FAQ",
        ],
    ),
    Phase(
        number=14,
        title="Data Residency, Localization & Payment Scope",
        timeline="Weeks 24-25",
        source_prompt="Addendum III",
        description="Document storage locations, localization, and payment-method scope decisions for the pilot.",
        bullets=[
            "Data residency and jurisdiction documentation",
            "Kiswahili translation support",
            "Language preference per tenant/user",
            "Scope decision for M-Pesa only vs multi-payment methods",
        ],
    ),
]

BUSINESS_READINESS_TRACK: List[str] = [
    "Terms of Service & Privacy Policy",
    "Data Processing Agreement (DPA)",
    "ODPC registration (Office of the Data Protection Commissioner)",
    "E&O / liability insurance",
    "Pricing/packaging",
    "One-page pilot agreement",
    "Support channel & SLA",
]


def get_phase(number: int) -> Optional[Phase]:
    """Retrieve Phase instance by phase number."""
    for phase in PHASES:
        if phase.number == number:
            return phase
    return None


def list_phases() -> List[Phase]:
    """Return a copy of all defined roadmap phases."""
    return PHASES.copy()


def list_business_readiness_items() -> List[str]:
    """Return a copy of all business and legal readiness track items."""
    return BUSINESS_READINESS_TRACK.copy()


def phase_as_markdown(phase: Phase) -> str:
    """Format a single Phase into Markdown representation."""
    lines = [
        f"## Phase {phase.number}: {phase.title}",
        f"- **Timeline:** {phase.timeline}",
        f"- **Source:** {phase.source_prompt}",
        f"- **Description:** {phase.description}",
        "- **Requirements:**",
    ]
    for bullet in phase.bullets:
        lines.append(f"  - {bullet}")
    return "\n".join(lines)


def as_markdown() -> str:
    """Format the complete roadmap into Markdown text."""
    lines = ["# PesaGuard Phased Roadmap\n"]
    for phase in PHASES:
        lines.append(phase_as_markdown(phase))
        lines.append("")
    lines.append("## Parallel Business & Operational Readiness Track")
    for item in BUSINESS_READINESS_TRACK:
        lines.append(f"- {item}")
    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Inspect the PesaGuard roadmap phases.")
    parser.add_argument("--list", action="store_true", help="List summary of all phases")
    parser.add_argument("--phase", type=int, help="Show details for a specific phase number")
    parser.add_argument("--business-track", action="store_true", help="List business readiness items")
    parser.add_argument("--json", action="store_true", help="Output phase details as JSON")
    args = parser.parse_args()

    if args.phase is not None:
        p = get_phase(args.phase)
        if not p:
            sys.exit(f"Error: Phase {args.phase} not found.")
        if args.json:
            print(json.dumps(p.to_dict(), indent=2))
        else:
            print(phase_as_markdown(p))
    elif args.business_track:
        if args.json:
            print(json.dumps(BUSINESS_READINESS_TRACK, indent=2))
        else:
            print("Parallel Business & Operational Readiness Track:\n")
            for item in BUSINESS_READINESS_TRACK:
                print(f"- {item}")
    elif args.list:
        for phase in PHASES:
            print(f"Phase {phase.number:02d}: {phase.title} ({phase.timeline})")
    else:
        if args.json:
            data = {
                "phases": [p.to_dict() for p in PHASES],
                "business_readiness_track": BUSINESS_READINESS_TRACK,
            }
            print(json.dumps(data, indent=2))
        else:
            print(as_markdown())
