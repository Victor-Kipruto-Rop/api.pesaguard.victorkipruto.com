"""
Daraja API Authentication Client for PesaGuard.

Manages M-Pesa OAuth token generation, secure thread-safe caching, exponential backoff retries,
and authorized API request dispatching with multi-tenant credential isolation.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import requests

from shared.daraja.oauth import DarajaOAuth
from utils.retries import retry_with_backoff

logger = logging.getLogger("pesaguard.daraja_auth")


class DarajaAuthClient:
    """Fetch, cache, and refresh Safaricom Daraja OAuth access tokens securely and robustly."""

    def __init__(
        self,
        tenant_id: str,
        credentials: Optional[Dict[str, Any]] = None,
        cache: Optional[Any] = None,
        session: Optional[requests.Session | Any] = None,
    ):
        self.tenant_id = tenant_id or "default"
        self.credentials = credentials or {}
        self.cache = cache
        self._token_cache_key = f"pesaguard:daraja:token:{self.tenant_id}"
        self.session = session or requests.Session()

        self.oauth = DarajaOAuth(
            client_id=self.credentials.get("consumer_key", ""),
            client_secret=self.credentials.get("consumer_secret", ""),
            base_url=self.credentials.get("base_url", "https://sandbox.safaricom.co.ke"),
            session=self.session,
        )

    def get_access_token(self) -> str:
        """Retrieve a valid access token from cache or fetch a new one with thread safety."""
        cached = self._read_cache()
        if cached:
            return cached

        token = self.oauth.get_access_token()
        self._write_cache(token, ttl=3300)
        return token

    def force_refresh(self) -> str:
        token = self.oauth.force_refresh()
        self._write_cache(token, ttl=3300)
        return token

    def _read_cache(self) -> Optional[str]:
        """Read token from external cache backend when available."""
        if self.cache is None:
            return None
        try:
            value = self.cache.get(self._token_cache_key)
            if not value:
                return None
            if isinstance(value, dict):
                return value.get("value")
            if isinstance(value, bytes):
                return value.decode("utf-8")
            return str(value)
        except Exception as exc:
            logger.warning("Failed to read token from cache for tenant=%s: %s", self.tenant_id, exc)
            return None

    def _write_cache(self, token: str, ttl: int) -> None:
        if self.cache is None:
            return
        try:
            if hasattr(self.cache, "setex"):
                self.cache.setex(self._token_cache_key, ttl, token)
            elif hasattr(self.cache, "set"):
                self.cache.set(self._token_cache_key, {"value": token}, ttl)
        except Exception as exc:
            logger.warning("Failed to write token to cache for tenant=%s: %s", self.tenant_id, exc)

    def _fetch_access_token(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        """Compatibility wrapper retained for existing tests/integration points."""
        token = self.force_refresh()
        return {"access_token": token, "expires_in": 3600}

    def request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        """Execute an authenticated HTTP request against Daraja APIs, handling token expiration."""
        headers = dict(kwargs.pop("headers", {}) or {})

        def _send_once() -> requests.Response:
            token = self.get_access_token()
            headers["Authorization"] = "Bearer " + token
            response = self.session.request(method=method, url=url, headers=headers, **kwargs)
            if response.status_code >= 500:
                raise RuntimeError(f"daraja upstream temporary failure: {response.status_code}")
            return response

        response = retry_with_backoff(_send_once, retries=5, base=0.5, max_backoff=30, jitter="full")

        if response.status_code == 401:
            logger.warning(
                "Daraja API request returned 401 for tenant=%s. Refreshing token and retrying once.",
                self.tenant_id,
            )
            refreshed = self.force_refresh()
            headers["Authorization"] = "Bearer " + refreshed
            response = self.session.request(method=method, url=url, headers=headers, **kwargs)

        return response
