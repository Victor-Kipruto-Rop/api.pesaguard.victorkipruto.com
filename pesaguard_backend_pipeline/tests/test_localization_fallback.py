import json
from pathlib import Path

import sys
sys.path.insert(0, 'pesaguard_backend_pipeline')
from localization_utils import format_ke_currency, format_ke_datetime, resolve_translation
from app_4_advanced_features import resolve_email_locale
from email_service import EmailService
from tenant_settings import TenantSettingsStore


ROOT = Path(__file__).resolve().parents[1]
EN_LOCALE = json.loads((ROOT / "dashboard" / "frontend" / "locales" / "en.json").read_text())
SW_LOCALE = json.loads((ROOT / "dashboard" / "frontend" / "locales" / "sw.json").read_text())


def test_missing_translation_falls_back_to_english():
    # Simulate an incomplete translation without changing the shipped catalog.
    incomplete_sw = {**SW_LOCALE, "email": dict(SW_LOCALE["email"])}
    del incomplete_sw["email"]["subject"]
    assert resolve_translation(incomplete_sw, "email.subject", EN_LOCALE) == EN_LOCALE["email"]["subject"]


def test_existing_translation_is_returned_without_fallback():
    assert SW_LOCALE["email"]["subject"] != EN_LOCALE["email"]["subject"]
    assert resolve_translation(SW_LOCALE, "email.subject", EN_LOCALE) == SW_LOCALE["email"]["subject"]


def test_camel_case_english_fallback():
    fallback = {"home": {"heroTitle": "Welcome"}}
    assert resolve_translation({}, "home.hero.title", fallback) == "Welcome"


def test_missing_key_in_both_catalogs_returns_key():
    assert resolve_translation(SW_LOCALE, "unknown.key", EN_LOCALE) == "unknown.key"


def test_tenant_locale_preference_resolves_from_settings(tmp_path):
    settings_path = tmp_path / "tenant-settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "default": {"preferred_locale": "sw"},
                "tenant-a": {"preferred_locale": "en"},
                "tenant-b": {
                    "preferred_locale": "sw",
                    "user_locale_overrides": {"user-2": "en"},
                },
            }
        ),
        encoding="utf-8",
    )

    store = TenantSettingsStore(str(settings_path))

    assert store.resolve_locale("tenant-a", "user-1") == "en"
    assert store.resolve_locale("tenant-b", "user-2") == "en"
    assert store.resolve_locale("tenant-b", "user-3") == "sw"


def test_ke_formatters_use_kenya_conventions():
    assert format_ke_currency(1000.5) == "KES 1,000.50"
    assert format_ke_datetime("2026-07-04T00:00:00Z") == "04 Jul 2026, 03:00 EAT"


def test_email_service_uses_locale_aware_subject_and_body():
    service = EmailService()
    html = service._build_escalation_html(
        {
            "anomaly_type": "duplicate_transfer",
            "severity": "high",
            "amount": 2500,
            "trans_id": "txn-123",
            "detected_at": "2026-07-04T00:00:00Z",
        },
        locale="sw",
    )

    assert "Kipindi kilichopandishwa" in html
    assert "Kiasi" in html
    assert "Msaada wa utendaji" in html


def test_resolve_email_locale_uses_tenant_settings_when_available(tmp_path):
    settings_path = tmp_path / "tenant-settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "default": {"preferred_locale": "en"},
                "tenant-a": {"preferred_locale": "sw"},
                "tenant-b": {
                    "preferred_locale": "en",
                    "user_locale_overrides": {"user-2": "sw"},
                },
            }
        ),
        encoding="utf-8",
    )

    assert resolve_email_locale("tenant-a", settings_path=settings_path) == "sw"
    assert resolve_email_locale("tenant-b", user_id="user-2", settings_path=settings_path) == "sw"


def test_nested_settings_updates_merge_without_losing_existing_values(tmp_path):
    settings_path = tmp_path / "tenant-settings.json"
    store = TenantSettingsStore(str(settings_path))

    store.update("tenant-x", {"thresholds": {"warning": 2000}})
    store.update("tenant-x", {"thresholds": {"critical": 6000}})

    saved_settings = store.get("tenant-x")
    assert saved_settings["thresholds"]["warning"] == 2000
    assert saved_settings["thresholds"]["critical"] == 6000


def test_locale_updates_are_normalized_on_persist(tmp_path):
    settings_path = tmp_path / "tenant-settings.json"
    store = TenantSettingsStore(str(settings_path))

    updated = store.update("tenant-x", {"preferred_locale": "EN-US"})

    assert updated["preferred_locale"] == "en"
    assert store.resolve_locale("tenant-x") == "en"
