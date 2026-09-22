"""
One-shot initialization script to construct database tables for PesaGuard.

Deployment / Usage:
  python3 init_db.py
"""

from __future__ import annotations

from environment import required_env

import logging
import os
import sys
from pathlib import Path

# Add project root directory dynamically to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from alembic import command
from alembic.config import Config

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("pesaguard.init_db")

DATABASE_URL = required_env("DATABASE_URL")


def main():
    logger.info("Applying Alembic migrations on %s...", DATABASE_URL.split("@")[-1])

    try:
        config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        config.set_main_option("sqlalchemy.url", DATABASE_URL)
        command.upgrade(config, "head")
        logger.info("Database migrations applied successfully.")
    except Exception as exc:
        logger.error("Failed to initialize database tables: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
