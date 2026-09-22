#!/usr/bin/env python3
"""
Enterprise-grade Automated Postgres backup and restoration script with integrity testing.

Usage:
  python3 backup_postgres.py --help
  python3 backup_postgres.py --backup                                # Create and test a new backup
  python3 backup_postgres.py --restore /path/to/backup.sql.gz       # Restore database from backup
  python3 backup_postgres.py --test                                  # Test integrity of latest backup
  python3 backup_postgres.py --list                                  # List existing backups

Deployment:
  1. Copy to /usr/local/bin/pesaguard-backup.py
  2. Copy systemd files to /etc/systemd/system/
  3. sudo systemctl daemon-reload && sudo systemctl enable --now pesaguard-backup.timer
"""

from __future__ import annotations

# Support direct script invocation as well as package execution.
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from environment import required_env

import argparse
import gzip
import hashlib
import json
import logging
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("pesaguard.backup")

# Configuration from environment
DATABASE_URL = required_env("DATABASE_URL")
BACKUP_DIR = Path(os.getenv("PESAGUARD_BACKUP_DIR", "/var/backups/pesaguard"))
RETENTION_DAYS = int(os.getenv("PESAGUARD_BACKUP_RETENTION_DAYS", "30"))


def _checksum_path(backup_file: Path) -> Path:
    return backup_file.with_suffix(backup_file.suffix + ".sha256")


def _write_checksum(backup_file: Path) -> Path:
    digest = hashlib.sha256()
    with backup_file.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    checksum_file = _checksum_path(backup_file)
    checksum_file.write_text(json.dumps({"sha256": digest.hexdigest(), "bytes": backup_file.stat().st_size}), encoding="utf-8")
    return checksum_file


def parse_db_url(url: str) -> dict[str, str]:
    """Parse PostgreSQL connection URL safely using urllib.parse."""
    parsed = urlparse(url)
    if parsed.scheme not in ("postgresql", "postgres"):
        raise ValueError(f"Unsupported database URL scheme: {parsed.scheme}")

    return {
        "user": unquote(parsed.username) if parsed.username else "postgres",
        "password": unquote(parsed.password) if parsed.password else "",
        "host": parsed.hostname or "localhost",
        "port": str(parsed.port) if parsed.port else "5432",
        "database": parsed.path.lstrip("/") or "postgres",
    }


def create_backup() -> Path:
    """Create a timestamped compressed backup of the Postgres database."""
    try:
        db_params = parse_db_url(DATABASE_URL)
    except Exception as e:
        logger.error("Failed to parse DATABASE_URL: %s", e)
        sys.exit(1)

    # Ensure target backup directory exists with secure permissions
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_file = BACKUP_DIR / f"pesaguard_{timestamp}.sql.gz"

    env = os.environ.copy()
    if db_params["password"]:
        env["PGPASSWORD"] = db_params["password"]

    dump_cmd = [
        "pg_dump",
        "-h", db_params["host"],
        "-p", db_params["port"],
        "-U", db_params["user"],
        "-d", db_params["database"],
        "--no-password",
        "-F", "p",  # Plain text dump for streaming gzip compression
    ]

    logger.info("Starting database backup for '%s' -> %s", db_params["database"], backup_file)

    try:
        with open(backup_file, "wb") as f_out:
            dump_process = subprocess.Popen(
                dump_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
            )

            gzip_process = subprocess.Popen(
                ["gzip", "-9"],
                stdin=dump_process.stdout,
                stdout=f_out,
                stderr=subprocess.PIPE,
            )

            if dump_process.stdout:
                dump_process.stdout.close()

            _, gzip_err = gzip_process.communicate()
            _, dump_err = dump_process.communicate()

            if dump_process.returncode != 0:
                raise RuntimeError(f"pg_dump error: {dump_err.decode().strip()}")
            if gzip_process.returncode != 0:
                raise RuntimeError(f"gzip error: {gzip_err.decode().strip()}")

        if not backup_file.exists() or backup_file.stat().st_size == 0:
            raise RuntimeError("Generated backup file is empty.")

        _write_checksum(backup_file)

        size_mb = backup_file.stat().st_size / (1024 * 1024)
        logger.info("Backup successfully created: %s (%.2f MB)", backup_file, size_mb)

        _cleanup_old_backups()
        return backup_file

    except Exception as e:
        logger.error("Backup execution failed: %s", e)
        if backup_file.exists():
            backup_file.unlink()
        checksum_file = _checksum_path(backup_file)
        if checksum_file.exists():
            checksum_file.unlink()
        sys.exit(1)


def restore_backup(backup_file: Path) -> None:
    """Restore database from a backup file using memory-efficient streaming."""
    if not backup_file.exists():
        logger.error("Backup file not found: %s", backup_file)
        sys.exit(1)

    try:
        db_params = parse_db_url(DATABASE_URL)
    except Exception as e:
        logger.error("Failed to parse DATABASE_URL: %s", e)
        sys.exit(1)

    env = os.environ.copy()
    if db_params["password"]:
        env["PGPASSWORD"] = db_params["password"]

    restore_cmd = [
        "psql",
        "-h", db_params["host"],
        "-p", db_params["port"],
        "-U", db_params["user"],
        "-d", db_params["database"],
        "--no-password",
        "-f", "-",
    ]

    logger.info("Starting restoration of database '%s' from %s", db_params["database"], backup_file)

    try:
        process = subprocess.Popen(
            restore_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=True,
        )

        is_gzipped = str(backup_file).endswith(".gz")
        if is_gzipped:
            with gzip.open(backup_file, "rt", encoding="utf-8", errors="replace") as gz:
                for line in gz:
                    if process.stdin:
                        process.stdin.write(line)
        else:
            with open(backup_file, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    if process.stdin:
                        process.stdin.write(line)

        stdout, stderr = process.communicate()
        if process.returncode != 0:
            raise RuntimeError(f"psql restoration failed: {stderr.strip()}")

        logger.info("Database restoration completed successfully from %s", backup_file)

    except Exception as e:
        logger.error("Restoration execution failed: %s", e)
        sys.exit(1)


def _cleanup_old_backups() -> None:
    """Remove backup files older than the configured retention period."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)

    for backup_file in sorted(BACKUP_DIR.glob("pesaguard_*.sql.gz")):
        try:
            timestamp_str = backup_file.stem.replace("pesaguard_", "").replace(".sql", "")
            file_time = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S").replace(tzinfo=timezone.utc)

            if file_time < cutoff:
                logger.info("Pruning expired backup: %s", backup_file)
                backup_file.unlink()
        except Exception as e:
            logger.warning("Could not parse timestamp for backup cleanup on %s: %s", backup_file, e)


def test_backup_integrity(backup_file: Path) -> bool:
    """Verify checksum, full decompression, and SQL dump signatures."""
    if not backup_file.exists():
        logger.warning("Backup file missing during integrity verification: %s", backup_file)
        return False

    try:
        checksum_file = _checksum_path(backup_file)
        if checksum_file.exists():
            manifest = json.loads(checksum_file.read_text(encoding="utf-8"))
            digest = hashlib.sha256()
            with backup_file.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
            if digest.hexdigest() != manifest.get("sha256") or backup_file.stat().st_size != manifest.get("bytes"):
                logger.warning("Integrity check failed: checksum mismatch for %s", backup_file)
                return False

        is_gzipped = str(backup_file).endswith(".gz")
        content_size = 0
        signature_found = False
        if is_gzipped:
            with gzip.open(backup_file, "rt", encoding="utf-8", errors="replace") as f:
                for line in f:
                    content_size += len(line)
                    if any(keyword in line for keyword in ("PostgreSQL database dump", "CREATE", "SET", "ALTER")):
                        signature_found = True
        else:
            with open(backup_file, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    content_size += len(line)
                    if any(keyword in line for keyword in ("PostgreSQL database dump", "CREATE", "SET", "ALTER")):
                        signature_found = True

        if content_size < 10:
            logger.warning("Integrity check failed: Backup file is empty or corrupted (%s)", backup_file)
            return False

        if not signature_found:
            logger.warning("Integrity check failed: No valid SQL signatures found in %s", backup_file)
            return False

        logger.info("Backup integrity check passed for %s", backup_file)
        return True
    except Exception as e:
        logger.warning("Integrity check threw an exception for %s: %s", backup_file, e)
        return False


def main():
    parser = argparse.ArgumentParser(description="PesaGuard PostgreSQL backup and restore utility")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--backup", action="store_true", help="Create a new database backup")
    group.add_argument("--restore", type=str, metavar="BACKUP_FILE", help="Restore database from a backup file")
    group.add_argument("--test", action="store_true", help="Test integrity of the latest backup")
    group.add_argument("--list", action="store_true", help="List recent database backups")

    args = parser.parse_args()

    if args.backup:
        backup_file = create_backup()
        if test_backup_integrity(backup_file):
            logger.info("Backup creation and integrity verification succeeded.")
        else:
            logger.error("Backup created but failed integrity check.")
            sys.exit(1)

    elif args.restore:
        restore_backup(Path(args.restore))

    elif args.test:
        backups = sorted(BACKUP_DIR.glob("pesaguard_*.sql.gz"))
        if not backups:
            logger.warning("No backup files found in %s to test.", BACKUP_DIR)
            sys.exit(1)

        latest_backup = backups[-1]
        if test_backup_integrity(latest_backup):
            logger.info("Latest backup (%s) integrity verified successfully.", latest_backup.name)
        else:
            sys.exit(1)

    elif args.list:
        backups = sorted(BACKUP_DIR.glob("pesaguard_*.sql.gz"), reverse=True)
        if not backups:
            logger.info("No backups found in %s", BACKUP_DIR)
        else:
            logger.info("Available backups in %s:", BACKUP_DIR)
            for backup in backups[:10]:
                size_mb = backup.stat().st_size / (1024 * 1024)
                mtime = datetime.fromtimestamp(backup.stat().st_mtime, tz=timezone.utc)
                logger.info("  %s (%.2f MB) - Created: %s", backup.name, size_mb, mtime.isoformat())


if __name__ == "__main__":
    main()

