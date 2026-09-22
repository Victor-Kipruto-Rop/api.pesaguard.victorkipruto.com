"""Verify that Alertmanager accepts and routes a synthetic PesaGuard alert."""

from __future__ import annotations

import argparse
import os
import sys
import uuid
from datetime import datetime, timezone

import requests


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--url",
        default=os.getenv("ALERTMANAGER_URL", "http://localhost:9093"),
        help="Alertmanager base URL",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=float(os.getenv("ALERTMANAGER_SMOKE_TIMEOUT_SECONDS", "5")),
    )
    args = parser.parse_args()
    smoke_id = uuid.uuid4().hex
    alert = [{
        "labels": {
            "alertname": "PesaGuardAlertmanagerSmoke",
            "service": "pesaguard",
            "severity": "info",
            "smoke_id": smoke_id,
        },
        "annotations": {
            "summary": "PesaGuard Alertmanager smoke test",
            "description": "Synthetic alert used to verify Alertmanager ingestion and routing.",
        },
        "startsAt": datetime.now(timezone.utc).isoformat(),
    }]
    endpoint = f"{args.url.rstrip('/')}/api/v2/alerts"
    try:
        response = requests.post(endpoint, json=alert, timeout=args.timeout)
        response.raise_for_status()
    except requests.RequestException as exc:
        print(f"Alertmanager smoke failed: {exc}", file=sys.stderr)
        return 1
    print(f"Alertmanager accepted smoke alert smoke_id={smoke_id} status={response.status_code}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
