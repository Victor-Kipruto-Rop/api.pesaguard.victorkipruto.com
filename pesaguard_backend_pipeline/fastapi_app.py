"""FastAPI control plane with the existing Flask API mounted below it."""

from __future__ import annotations

import os
from typing import Any, Dict

try:
    from fastapi import FastAPI
    from fastapi.middleware.wsgi import WSGIMiddleware
except ImportError as exc:  # pragma: no cover - exercised in dependency installation
    raise RuntimeError("FastAPI control plane requires fastapi and uvicorn dependencies") from exc

from .api.dashboard_app import create_app as create_dashboard_app
from .health import build_health_payload


app = FastAPI(
    title="PesaGuard Control Plane",
    version=os.getenv("PESAGUARD_RELEASE", "1"),
    docs_url="/docs",
    redoc_url="/redoc",
)


@app.get("/health")
def health() -> Dict[str, Any]:
    """Expose the platform health contract through the ASGI control plane."""
    return build_health_payload()


# The Flask application remains the implementation owner for existing routes.
# Mounting it keeps the migration incremental while FastAPI owns the process.
app.mount("/", WSGIMiddleware(create_dashboard_app()))