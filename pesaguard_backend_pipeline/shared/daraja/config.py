"""
Multi-Tenant Daraja Configuration Loader for PesaGuard.

Securely loads Safaricom Daraja API credentials (Consumer Key, Consumer Secret, Base URL)
from environment variables with tenant-specific prefixing and fallback support.
"""

from __future__ import annotations

import os
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("pesaguard.daraja_config")


class DarajaConfig:
    """Load per-tenant Daraja credentials from environment variables securely."""

    def __init__(self, tenant_id: Optional[str] = None):
        self.tenant_id = (tenant_id or os.getenv("TENANT_ID", "default")).strip().lower()
        env_prefix = self.tenant_id.upper().replace("-", "_")

        # Support both correct spelling ('daraja') and legacy typo ('darja') for backward compatibility
        consumer_key = (
            os.getenv(f"{env_prefix}_DARAJA_CONSUMER_KEY")
            or os.getenv(f"{env_prefix}_DARJA_CONSUMER_KEY")
            or os.getenv("DARAJA_CONSUMER_KEY")
            or os.getenv("DARJA_CONSUMER_KEY", "")
        )

        consumer_secret = (
            os.getenv(f"{env_prefix}_DARAJA_CONSUMER_SECRET")
            or os.getenv(f"{env_prefix}_DARJA_CONSUMER_SECRET")
            or os.getenv("DARAJA_CONSUMER_SECRET")
            or os.getenv("DARJA_CONSUMER_SECRET", "")
        )

        base_url = (
            os.getenv(f"{env_prefix}_DARAJA_BASE_URL")
            or os.getenv("DARAJA_BASE_URL")
            or os.getenv("DARJA_BASE_URL", "https://sandbox.safaricom.co.ke")
        ).rstrip("/")

        self._credentials: Dict[str, Any] = {
            "tenant_id": self.tenant_id,
            "consumer_key": consumer_key.strip(),
            "consumer_secret": consumer_secret.strip(),
            "base_url": base_url,
        }

        if not self._credentials["consumer_key"] or not self._credentials["consumer_secret"]:
            logger.warning(
                "Daraja credentials incomplete for tenant=%s. API calls may fail until credentials are configured.",
                self.tenant_id,
            )

    def get_credentials(self) -> Dict[str, Any]:
        """Return a copy of the loaded credential dictionary."""
        return dict(self._credentials)

    @property
    def is_configured(self) -> bool:
        """Verify whether essential API keys are present."""
        return bool(self._credentials.get("consumer_key") and self._credentials.get("consumer_secret"))
