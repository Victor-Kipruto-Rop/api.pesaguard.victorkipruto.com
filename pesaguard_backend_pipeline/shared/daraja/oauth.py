from __future__ import annotations

import json
import logging
import os
import threading
import time
from hashlib import sha256
from typing import Any, Dict, Optional

import requests

from utils.retries import retry_with_backoff

logger = logging.getLogger("pesaguard.daraja_oauth")


class DarajaOAuth:
    """Thread-safe Daraja OAuth token manager with optional Redis durability."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        base_url: str,
        session: Optional[requests.Session | Any] = None,
    ):
        self.client_id = (client_id or "").strip()
        self.client_secret = (client_secret or "").strip()
        self.base_url = (base_url or "https://sandbox.safaricom.co.ke").rstrip("/")
        self.session = session or requests.Session()
        self._token: Optional[str] = None
        self._expires_at: float = 0.0
        self._lock = threading.Lock()
        self._redis_client = None

        cache_identity = f"{self.base_url}:{self.client_id}"
        cache_hash = sha256(cache_identity.encode("utf-8")).hexdigest()[:20]
        self._redis_key = f"pesaguard:daraja:oauth:{cache_hash}"

    def get_access_token(self) -> str:
        if self._token and time.time() < self._expires_at:
            return self._token

        with self._lock:
            if self._token and time.time() < self._expires_at:
                return self._token

            cached = self._read_redis_cache()
            if cached:
                self._token = cached["token"]
                self._expires_at = cached["expires_at"]
                return self._token

            token, expires_at = self._fetch_and_cache_token()
            self._token = token
            self._expires_at = expires_at
            return token

    def force_refresh(self) -> str:
        with self._lock:
            self._token = None
            self._expires_at = 0.0
            token, expires_at = self._fetch_and_cache_token()
            self._token = token
            self._expires_at = expires_at
            return token

    def _fetch_and_cache_token(self) -> tuple[str, float]:
        def _call() -> requests.Response:
            url = f"{self.base_url}/oauth/v1/generate?grant_type=client_credentials"
            response = self.session.get(url, auth=(self.client_id, self.client_secret), timeout=10)
            if response.status_code >= 500:
                raise RuntimeError(f"daraja oauth temporary failure: {response.status_code}")
            return response

        response = retry_with_backoff(_call, retries=5, base=0.5, max_backoff=30, jitter="full")
        if response.status_code != 200:
            raise RuntimeError(f"daraja oauth failed: {response.status_code} {response.text}")

        body = response.json()
        token = str(body.get("access_token") or "").strip()
        if not token:
            raise RuntimeError("daraja oauth response missing access_token")

        expires_in = int(body.get("expires_in") or 3600)
        safe_ttl = max(30, expires_in - 30)
        expires_at = time.time() + safe_ttl
        self._write_redis_cache(token=token, expires_at=expires_at, ttl=safe_ttl)
        return token, expires_at

    def _get_redis_client(self):
        if self._redis_client is not None:
            return self._redis_client

        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            return None

        try:
            import redis

            self._redis_client = redis.from_url(redis_url, socket_connect_timeout=2, socket_timeout=2)
            return self._redis_client
        except Exception as exc:
            logger.warning("Redis unavailable for OAuth durable cache: %s", exc)
            return None

    def _read_redis_cache(self) -> Optional[Dict[str, Any]]:
        client = self._get_redis_client()
        if client is None:
            return None

        try:
            raw = client.get(self._redis_key)
            if not raw:
                return None
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
            payload = json.loads(raw)
            token = str(payload.get("token") or "").strip()
            expires_at = float(payload.get("expires_at") or 0)
            if not token or time.time() >= expires_at:
                return None
            return {"token": token, "expires_at": expires_at}
        except Exception as exc:
            logger.warning("Failed reading OAuth redis cache: %s", exc)
            return None

    def _write_redis_cache(self, token: str, expires_at: float, ttl: int) -> None:
        client = self._get_redis_client()
        if client is None:
            return

        try:
            payload = json.dumps({"token": token, "expires_at": expires_at})
            client.setex(self._redis_key, max(1, int(ttl)), payload)
        except Exception as exc:
            logger.warning("Failed writing OAuth redis cache: %s", exc)
