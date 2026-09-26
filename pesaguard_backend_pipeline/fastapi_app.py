"""FastAPI control plane with the existing Flask API mounted below it."""

from __future__ import annotations

import os
from typing import Any, Dict

try:
    from fastapi import FastAPI
    from fastapi.middleware.wsgi import WSGIMiddleware
    from fastapi.responses import JSONResponse
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


@app.get("/livez")
def livez() -> Dict[str, str]:
    """Liveness probe: the process is up and serving. Checks no dependencies.

    Used by the container HEALTHCHECK, which runs often and must not depend on
    Kafka, Redis or Safaricom being reachable.
    """
    return {"status": "alive"}


@app.get("/health")
def health() -> JSONResponse:
    """Expose the platform health contract through the ASGI control plane.

    The body is unchanged. The HTTP status now reflects it: 503 when the
    database is unreachable (overall status "failed"), 200 otherwise, so a load
    balancer or orchestrator probing this endpoint can see a broken instance.
    "degraded" (an optional dependency is down) stays 200 so a Kafka, Redis or
    Daraja outage does not take every instance out of rotation.
    """
    payload = build_health_payload()
    return JSONResponse(payload, status_code=503 if payload.get("status") == "failed" else 200)


# The Flask application remains the implementation owner for existing routes.
# Mounting it keeps the migration incremental while FastAPI owns the process.
app.mount("/", WSGIMiddleware(create_dashboard_app()))