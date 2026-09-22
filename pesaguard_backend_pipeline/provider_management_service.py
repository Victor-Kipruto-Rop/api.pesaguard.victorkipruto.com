from __future__ import annotations

import base64
import hashlib
import json
import os
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

from sqlalchemy.orm import Session, sessionmaker
from cryptography.fernet import Fernet, InvalidToken

from models import PaymentProvider


class ProviderManagementService:
    """Manage tenant-scoped payment providers and their operational state."""

    _secret_keys = {
        "secret", "client_secret", "api_key", "access_token", "private_key", "password",
        "consumer_key", "consumer_secret", "token",
    }
    _provider_statuses = {"active", "inactive", "disabled", "maintenance"}

    def __init__(self, session_factory: sessionmaker):
        self.session_factory = session_factory
        configured_key = os.getenv("PROVIDER_ENCRYPTION_KEY")
        if not configured_key and os.getenv("PESAGUARD_ENVIRONMENT", "development").lower() not in {"production", "prod"}:
            configured_key = os.getenv("JWT_SECRET_KEY")
        if not configured_key:
            raise RuntimeError("PROVIDER_ENCRYPTION_KEY must be configured")
        self._fernet = self._build_fernet(configured_key)
        previous_key = os.getenv("PROVIDER_ENCRYPTION_KEY_PREVIOUS")
        self._previous_fernet = self._build_fernet(previous_key) if previous_key else None

    @staticmethod
    def _build_fernet(configured_key: str) -> Fernet:
        key = base64.urlsafe_b64encode(hashlib.sha256(configured_key.encode("utf-8")).digest())
        return Fernet(key)

    def _encrypt_value(self, value: Any) -> str:
        plaintext = json.dumps(value, separators=(",", ":"), allow_nan=False).encode("utf-8")
        return "enc:v1:" + self._fernet.encrypt(plaintext).decode("ascii")

    def _decrypt_value(self, value: Any) -> Any:
        if not isinstance(value, str) or not value.startswith("enc:v1:"):
            return value
        for cipher in (self._fernet, self._previous_fernet):
            if cipher is None:
                continue
            try:
                plaintext = cipher.decrypt(value[7:].encode("ascii"))
                return json.loads(plaintext)
            except (InvalidToken, ValueError, TypeError, json.JSONDecodeError):
                continue
        raise ValueError("Unable to decrypt provider configuration")

    def _protect_configuration(self, value: Any, protect_all: bool = False, parent_key: Optional[str] = None) -> Any:
        if isinstance(value, dict):
            return {
                key: self._protect_configuration(
                    item,
                    protect_all=protect_all or key.lower() in self._secret_keys,
                    parent_key=key,
                )
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [self._protect_configuration(item, protect_all=protect_all, parent_key=parent_key) for item in value]
        return self._encrypt_value(value) if protect_all else value

    def _unprotect_configuration(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {key: self._unprotect_configuration(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._unprotect_configuration(item) for item in value]
        return self._decrypt_value(value)

    @classmethod
    def _redact(cls, value: Any, key: Optional[str] = None) -> Any:
        if key and key.lower() in cls._secret_keys:
            return "********"
        if isinstance(value, dict):
            return {item_key: cls._redact(item_value, item_key) for item_key, item_value in value.items()}
        if isinstance(value, list):
            return [cls._redact(item) for item in value]
        return value

    @classmethod
    def _serialize(cls, provider: PaymentProvider) -> Dict[str, Any]:
        return {
            "id": provider.id,
            "tenant_id": provider.tenant_id,
            "name": provider.name,
            "provider_type": provider.provider_type,
            "status": provider.status,
            "credentials": cls._redact(provider.credentials or {}),
            "api_configuration": cls._redact(provider.api_configuration or {}),
            "account_configuration": cls._redact(provider.account_configuration or {}),
            "metadata": cls._redact(provider.provider_metadata or {}),
            "supported_currencies": provider.supported_currencies or [],
            "capabilities": provider.capabilities or [],
            "webhook_configuration": cls._redact(provider.webhook_configuration or {}),
            "connection_status": provider.connection_status,
            "connection_checked_at": provider.connection_checked_at.isoformat() if provider.connection_checked_at else None,
            "health_status": provider.health_status,
            "health_details": provider.health_details or {},
            "created_at": provider.created_at.isoformat() if provider.created_at else None,
            "updated_at": provider.updated_at.isoformat() if provider.updated_at else None,
        }

    def register(self, tenant_id: str, name: str, provider_type: str = "payment", **configuration: Any) -> Dict[str, Any]:
        if not str(tenant_id or "").strip():
            raise ValueError("Tenant ID is required")
        if not str(name or "").strip():
            raise ValueError("Provider name is required")
        session: Session = self.session_factory()
        try:
            provider = PaymentProvider(
                id=f"provider_{uuid.uuid4().hex[:12]}",
                tenant_id=str(tenant_id),
                name=str(name).strip(),
                provider_type=str(provider_type or "payment"),
                status=str(configuration.get("status") or "active"),
                credentials=self._protect_configuration(dict(configuration.get("credentials") or {}), protect_all=True),
                api_configuration=self._protect_configuration(dict(configuration.get("api_configuration") or {})),
                account_configuration=self._protect_configuration(dict(configuration.get("account_configuration") or {})),
                provider_metadata=dict(configuration.get("metadata") or {}),
                supported_currencies=list(configuration.get("supported_currencies") or []),
                capabilities=list(configuration.get("capabilities") or []),
                webhook_configuration=self._protect_configuration(dict(configuration.get("webhook_configuration") or {})),
            )
            if provider.status not in self._provider_statuses:
                raise ValueError("Unsupported provider status")
            session.add(provider)
            session.commit()
            session.refresh(provider)
            return self._serialize(provider)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def list(self, tenant_id: str) -> list[Dict[str, Any]]:
        if not str(tenant_id or "").strip():
            return []
        session: Session = self.session_factory()
        try:
            providers = session.query(PaymentProvider).filter_by(tenant_id=str(tenant_id)).order_by(PaymentProvider.name).all()
            return [self._serialize(provider) for provider in providers]
        finally:
            session.close()

    def get(self, tenant_id: str, provider_id: str) -> Optional[Dict[str, Any]]:
        if not str(tenant_id or "").strip():
            return None
        session: Session = self.session_factory()
        try:
            provider = session.query(PaymentProvider).filter_by(id=provider_id, tenant_id=str(tenant_id)).first()
            return self._serialize(provider) if provider else None
        finally:
            session.close()

    def update(self, tenant_id: str, provider_id: str, patch: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not str(tenant_id or "").strip():
            return None
        allowed = {"name", "provider_type", "status", "credentials", "api_configuration", "account_configuration", "metadata", "supported_currencies", "capabilities", "webhook_configuration"}
        session: Session = self.session_factory()
        try:
            provider = session.query(PaymentProvider).filter_by(id=provider_id, tenant_id=str(tenant_id)).first()
            if provider is None:
                return None
            for key in allowed.intersection(patch):
                value = patch[key]
                if key == "metadata":
                    value = dict(value or {})
                    setattr(provider, "provider_metadata", value)
                    continue
                if key in {"credentials", "api_configuration", "account_configuration", "webhook_configuration"}:
                    value = self._protect_configuration(
                        dict(value or {}),
                        protect_all=key == "credentials",
                    )
                elif key in {"supported_currencies", "capabilities"}:
                    value = list(value or [])
                setattr(provider, key, value)
            provider.updated_at = datetime.now(timezone.utc)
            session.commit()
            session.refresh(provider)
            return self._serialize(provider)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_decrypted_configuration(self, tenant_id: str, provider_id: str) -> Optional[Dict[str, Any]]:
        """Return decrypted provider configuration for a single outbound operation."""
        if not str(tenant_id or "").strip():
            return None
        session: Session = self.session_factory()
        try:
            provider = session.query(PaymentProvider).filter_by(id=provider_id, tenant_id=str(tenant_id)).first()
            if provider is None:
                return None
            return {
                "credentials": self._unprotect_configuration(provider.credentials or {}),
                "api_configuration": self._unprotect_configuration(provider.api_configuration or {}),
                "account_configuration": self._unprotect_configuration(provider.account_configuration or {}),
                "webhook_configuration": self._unprotect_configuration(provider.webhook_configuration or {}),
            }
        finally:
            session.close()

    @contextmanager
    def outbound_configuration(self, tenant_id: str, provider_id: str):
        """Expose decrypted configuration only for the duration of a provider call."""
        configuration = self.get_decrypted_configuration(tenant_id, provider_id)
        if configuration is None:
            raise LookupError("Provider not found")
        try:
            yield configuration
        finally:
            configuration.clear()

    def execute_outbound(self, tenant_id: str, provider_id: str, operation: Callable[[Dict[str, Any]], Any]) -> Any:
        """Run a provider operation with decrypted configuration scoped to its callback."""
        with self.outbound_configuration(tenant_id, provider_id) as configuration:
            return operation(configuration)

    def rotate_provider_configuration(self, tenant_id: str, provider_id: str) -> bool:
        """Re-encrypt one provider using the current key after a key rotation."""
        if not str(tenant_id or "").strip():
            return False
        session: Session = self.session_factory()
        try:
            provider = session.query(PaymentProvider).filter_by(id=provider_id, tenant_id=str(tenant_id)).first()
            if provider is None:
                return False
            credentials = self._unprotect_configuration(provider.credentials or {})
            api_configuration = self._unprotect_configuration(provider.api_configuration or {})
            account_configuration = self._unprotect_configuration(provider.account_configuration or {})
            webhook_configuration = self._unprotect_configuration(provider.webhook_configuration or {})
            provider.credentials = self._protect_configuration(credentials, protect_all=True)
            provider.api_configuration = self._protect_configuration(api_configuration)
            provider.account_configuration = self._protect_configuration(account_configuration)
            provider.webhook_configuration = self._protect_configuration(webhook_configuration)
            provider.updated_at = datetime.now(timezone.utc)
            session.commit()
            return True
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def update_connection(self, tenant_id: str, provider_id: str, status: str, details: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        return self._update_operational(tenant_id, provider_id, connection_status=status, health_details=details or {})

    def update_health(self, tenant_id: str, provider_id: str, status: str, details: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        return self._update_operational(tenant_id, provider_id, health_status=status, health_details=details or {})

    def _update_operational(self, tenant_id: str, provider_id: str, **values: Any) -> Optional[Dict[str, Any]]:
        if not str(tenant_id or "").strip():
            return None
        session: Session = self.session_factory()
        try:
            provider = session.query(PaymentProvider).filter_by(id=provider_id, tenant_id=str(tenant_id)).first()
            if provider is None:
                return None
            for key, value in values.items():
                setattr(provider, key, value)
            now = datetime.now(timezone.utc)
            provider.connection_checked_at = now
            provider.updated_at = now
            session.commit()
            session.refresh(provider)
            return self._serialize(provider)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()