"""Canonical PesaGuard dashboard API entry point."""

from __future__ import annotations

import os

from .app_2 import create_app

app = create_app()


if __name__ == "__main__":
    app.run(
        host=os.getenv("PESAGUARD_BIND_HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "5001")),
        debug=os.getenv("FLASK_DEBUG", "false").lower() in {"true", "1", "yes"},
    )
