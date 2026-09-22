import sys
sys.path.insert(0, 'pesaguard_backend_pipeline')
import phase_manager


def test_phase_count():
    assert len(phase_manager.PHASES) == 15


def test_phase_titles():
    expected_titles = [
        "Discovery & Validation",
        "Core Pipeline",
        "Real Matching & Reconciliation Logic",
        "Alerting System",
        "Monitoring & Observability",
        "Dashboards (Operational + Customer)",
        "Security & API Protection",
        "Backup, DR & Data Retention",
        "Incident Response Tooling",
        "API Documentation",
        "Testing & Hardening",
        "Deployment & Launch",
        "Operational Gaps",
        "Tenant Lifecycle, Threat Model, Feature Flags, Billing, Help Docs",
        "Data Residency, Localization & Payment Scope",
    ]
    assert [phase.title for phase in phase_manager.PHASES] == expected_titles


def test_business_readiness_items():
    assert "Terms of Service & Privacy Policy" in phase_manager.BUSINESS_READINESS_TRACK
    assert len(phase_manager.BUSINESS_READINESS_TRACK) == 7
