"""Load backend environment settings without importing application services."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


def load_backend_env(env_path: str | os.PathLike[str] | None = None) -> bool:
    """Fill missing process variables; never search the current working directory.

    PESAGUARD_ENV_FILE selects an explicit deployment file. Set
    PYTHON_DOTENV_DISABLED=1 for environment-only deployments and isolated tests.
    Values are literal (no ${...} expansion), including secrets containing '$'.
    """
    if os.getenv("PYTHON_DOTENV_DISABLED", "").lower() in {"1", "true", "yes", "on"}:
        return False
    configured_path = env_path if env_path is not None else os.getenv("PESAGUARD_ENV_FILE")
    path = Path(configured_path) if configured_path is not None else DEFAULT_ENV_FILE
    if not path.is_file():
        if configured_path is not None:
            raise RuntimeError("Configured backend environment file is not available")
        return False
    return load_dotenv(path, override=False, interpolate=False, encoding="utf-8-sig")


def required_env(name: str) -> str:
    """Require an explicit value without including it in errors or logs."""
    value = os.getenv(name)
    if value is None or not value.strip():
        raise RuntimeError(f"{name} must be configured")
    return value


load_backend_env()
