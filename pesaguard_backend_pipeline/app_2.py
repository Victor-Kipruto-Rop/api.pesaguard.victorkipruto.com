"""Compatibility import for the canonical dashboard API."""

from __future__ import annotations

import sys

from pesaguard_backend_pipeline.api import dashboard_app as _dashboard_app

sys.modules[__name__] = _dashboard_app