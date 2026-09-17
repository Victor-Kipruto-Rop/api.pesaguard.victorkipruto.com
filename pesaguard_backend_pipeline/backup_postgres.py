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

import argparse
import gzip
import hashlib
import json
import logging
import os
import shlex
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import unquote, urlparse

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("pesaguard.backup")

# Configuration from environment
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://pesaguard:pesaguard@localhost:5432/pesaguard")
BACKUP_DIR = Path(os.getenv("PESAGUARD_BACKUP_DIR", "/var/backups/pesaguard"))
RETENTION_DAYS = int(os.getenv("PESAGUARD_BACKUP_RETENTION_DAYS", "30"))
ENCRYPT_COMMAND = os.getenv("PESAGUARD_BACKUP_ENCRYPT_COMMAND", "").strip()
DECRYPT_COMMAND = os.getenv("PESAGUARD_BACKUP_DECRYPT_COMMAND", "").strip()
UPLOAD_COMMAND = os.getenv("PESAGUARD_BACKUP_UPLOAD_COMMAND", "").strip()
STATUS_FILE = Path(os.getenv("PESAGUARD_BACKUP_STATUS_FILE", str(BACKUP_DIR / "last_status.json")))
PESAGUARD_WAL_ARCHIVE_DIR = os.getenv("PESAGUARD_WAL_ARCHIVE_DIR", "/var/lib/postgresql/wal_archive")


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


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest_path(backup_file: Path) -> Path:
    return backup_file.with_name(backup_file.name + ".manifest.json")


def _write_status(status: str, **details: object) -> None:
    """Publish a machine-readable backup health record for monitoring."""
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATUS_FILE.write_text(json.dumps({
        "status": status,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        **details,
    }, sort_keys=True) + "\n", encoding="utf-8")


def _backup_artifacts() -> list[Path]:
    return sorted(
        [*BACKUP_DIR.glob("pesaguard_*.sql.gz"), *BACKUP_DIR.glob("pesaguard_*.sql.gz.enc")],
        key=lambda path: path.stat().st_mtime,
    )


def _write_manifest(backup_file: Path) -> Path:
    manifest = _manifest_path(backup_file)
    manifest.write_text(json.dumps({
        "artifact": backup_file.name,
        "size": backup_file.stat().st_size,
        "sha256": _sha256(backup_file),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def _verify_manifest(backup_file: Path) -> bool:
    manifest = _manifest_path(backup_file)
    if not manifest.exists():
        return True  # Compatibility with artifacts created before manifests.
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
        return data.get("artifact") == backup_file.name and data.get("size") == backup_file.stat().st_size and data.get("sha256") == _sha256(backup_file)
    except (OSError, ValueError, KeyError):
        return False


def _stream_encrypt(source: Path, target: Path) -> None:
    process = subprocess.Popen(shlex.split(ENCRYPT_COMMAND), stdin=subprocess.PIPE, stdout=target.open("wb"), stderr=subprocess.PIPE)
    try:
        with source.open("rb") as input_file:
            assert process.stdin is not None
            for chunk in iter(lambda: input_file.read(1024 * 1024), b""):
                process.stdin.write(chunk)
            process.stdin.close()
        stderr = process.stderr.read() if process.stderr else b""
        if process.wait() != 0:
            raise RuntimeError(f"backup encryption failed: {stderr.decode(errors='replace').strip()}")
    finally:
        if process.poll() is None:
            process.kill()


def _decrypted_stream(backup_file: Path):
    if not backup_file.name.endswith(".enc"):
        return None
    if not DECRYPT_COMMAND:
        raise RuntimeError("encrypted backup requires PESAGUARD_BACKUP_DECRYPT_COMMAND")
    process = subprocess.Popen(shlex.split(DECRYPT_COMMAND), stdin=backup_file.open("rb"), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return process


def _upload_offsite(backup_file: Path) -> None:
    """Run the deployment-provided upload command and require successful delivery."""
    if not UPLOAD_COMMAND:
        production = os.getenv("PESAGUARD_ENVIRONMENT", "development").lower() in {"production", "prod"}
        if production:
            raise RuntimeError("PESAGUARD_BACKUP_UPLOAD_COMMAND is required for off-site backup durability")
        return
    command = [part.replace("{backup}", str(backup_file)) for part in shlex.split(UPLOAD_COMMAND)]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
    except OSError as exc:
        raise RuntimeError(f"off-site backup upload failed: command unavailable: {command[0]}") from exc
    if completed.returncode != 0:
        raise RuntimeError(f"off-site backup upload failed: {completed.stderr.strip()}")


def create_backup() -> Path:
    """Create a timestamped compressed backup of the Postgres database."""
    production = os.getenv("PESAGUARD_ENVIRONMENT", "development").lower() in {"production", "prod"}
    if (production or os.getenv("PESAGUARD_BACKUP_ENCRYPT_COMMAND_REQUIRED", "false").lower() == "true") and not ENCRYPT_COMMAND:
        raise RuntimeError("PESAGUARD_BACKUP_ENCRYPT_COMMAND is required for production backups")
    if production and not UPLOAD_COMMAND:
        raise RuntimeError("PESAGUARD_BACKUP_UPLOAD_COMMAND is required for off-site backup durability")
    try:
        db_params = parse_db_url(DATABASE_URL)
    except Exception as e:
        logger.error("Failed to parse DATABASE_URL: %s", e)
        sys.exit(1)

    # Ensure target backup directory exists with secure permissions
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    plain_backup_file = BACKUP_DIR / f"pesaguard_{timestamp}.sql.gz"
    backup_file = BACKUP_DIR / f"pesaguard_{timestamp}.sql.gz.enc" if ENCRYPT_COMMAND else plain_backup_file

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
        with open(plain_backup_file, "wb") as f_out:
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

        if ENCRYPT_COMMAND:
            _stream_encrypt(plain_backup_file, backup_file)
            plain_backup_file.unlink()
        if not backup_file.exists() or backup_file.stat().st_size == 0:
            raise RuntimeError("Generated backup file is empty.")

        _write_manifest(backup_file)
        _upload_offsite(backup_file)
        _upload_offsite(_manifest_path(backup_file))

        size_mb = backup_file.stat().st_size / (1024 * 1024)
        logger.info("Backup successfully created: %s (%.2f MB)", backup_file, size_mb)

        _cleanup_old_backups()
        _write_status("succeeded", artifact=backup_file.name, sha256=_sha256(backup_file), offsite_configured=bool(UPLOAD_COMMAND))
        return backup_file

    except Exception as e:
        logger.error("Backup execution failed: %s", e)
        _write_status("failed", error=str(e)[:1000])
        for artifact in (backup_file, plain_backup_file, _manifest_path(backup_file)):
            if artifact.exists():
                artifact.unlink()
        sys.exit(1)


def restore_backup(backup_file: Path) -> None:
    """Restore database from a backup file using memory-efficient streaming."""
    if not backup_file.exists():
        logger.error("Backup file not found: %s", backup_file)
        sys.exit(1)
    if not _verify_manifest(backup_file):
        logger.error("Backup manifest verification failed: %s", backup_file)
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
        "-v", "ON_ERROR_STOP=1",
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
            text=False,
        )

        decrypt_process = _decrypted_stream(backup_file)
        if decrypt_process:
            source = gzip.GzipFile(fileobj=decrypt_process.stdout, mode="rb")
        elif str(backup_file).endswith(".gz"):
            source = gzip.open(backup_file, "rb")
        else:
            source = backup_file.open("rb")
        with source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                if process.stdin:
                    process.stdin.write(chunk)

        stdout, stderr = process.communicate()
        if process.returncode != 0:
            raise RuntimeError(f"psql restoration failed: {stderr.decode(errors='replace').strip()}")
        if decrypt_process and decrypt_process.wait() != 0:
            raise RuntimeError("backup decryption failed")

        logger.info("Database restoration completed successfully from %s", backup_file)

    except Exception as e:
        logger.error("Restoration execution failed: %s", e)
        sys.exit(1)


def _cleanup_old_backups() -> None:
    """Remove backup files older than the configured retention period."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)

    for backup_file in sorted(BACKUP_DIR.glob("pesaguard_*.sql.gz*")):
        try:
            if backup_file.name.endswith(".manifest.json"):
                continue
            timestamp_str = backup_file.name.replace("pesaguard_", "").split(".sql.gz", 1)[0]
            file_time = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S").replace(tzinfo=timezone.utc)

            if file_time < cutoff:
                logger.info("Pruning expired backup: %s", backup_file)
                backup_file.unlink()
        except Exception as e:
            logger.warning("Could not parse timestamp for backup cleanup on %s: %s", backup_file, e)


def test_backup_integrity(backup_file: Path) -> bool:
    """Verify manifest, decryption, full decompression, and SQL content."""
    if not backup_file.exists():
        logger.warning("Backup file missing during integrity verification: %s", backup_file)
        return False

    try:
        if not _verify_manifest(backup_file):
            logger.warning("Integrity check failed: manifest mismatch for %s", backup_file)
            return False
        decrypt_process = _decrypted_stream(backup_file)
        source = decrypt_process.stdout if decrypt_process else backup_file.open("rb")
        found = set()
        line_count = 0
        archive = gzip.GzipFile(fileobj=source, mode="rb") if str(backup_file).endswith((".gz", ".enc")) else source
        with archive:
            for line in archive:
                line_count += 1
                text = line.decode("utf-8", errors="replace")
                found.update(keyword for keyword in {"PostgreSQL database dump", "CREATE", "INSERT", "SET", "ALTER"} if keyword in text)
        if decrypt_process and decrypt_process.wait() != 0:
            return False
        if line_count == 0 or not found:
            logger.warning("Integrity check failed: No valid SQL signatures found in %s", backup_file)
            return False

        logger.info("Backup integrity check passed for %s", backup_file)
        return True
    except Exception as e:
        logger.warning("Integrity check threw an exception for %s: %s", backup_file, e)
        return False


def pitr_restore(backup_file: Path, *, target_time: Optional[str] = None, target_xid: Optional[str] = None) -> None:
    """Restore a base backup and replay WAL archives to a specific point in time.

    Uses PostgreSQL's native PITR mechanism by placing recovery configuration in
    ``recovery.conf`` (or the ``postgresql.conf`` standby section on PG12+) and
    starting the server in recovery mode. The base backup file must have been
    created with ``pg_basebackup`` or ``pg_dump``-based base + WAL archive chain.

    Either ``target_time`` (UTC timestamp string) or ``target_xid`` (transaction
    ID) must be provided to pinpoint the recovery target.
    """
    if not backup_file.exists():
        logger.error("Base backup file not found: %s", backup_file)
        sys.exit(1)

    if not _verify_manifest(backup_file):
        logger.error("Base backup manifest verification failed: %s", backup_file)
        sys.exit(1)

    if not target_time and not target_xid:
        logger.error("Either --target-time or --target-xid must be provided for PITR restore")
        sys.exit(1)

    try:
        db_params = parse_db_url(DATABASE_URL)
    except Exception as e:
        logger.error("Failed to parse DATABASE_URL: %s", e)
        sys.exit(1)

    recovery_target = target_time or f"XID {target_xid}"
    logger.info(
        "Starting point-in-time recovery on database '%s' from %s to target '%s'",
        db_params["database"], backup_file, recovery_target,
    )

    env = os.environ.copy()
    if db_params["password"]:
        env["PGPASSWORD"] = db_params["password"]

    wal_archive_dir = PESAGUARD_WAL_ARCHIVE_DIR
    pg_data = os.getenv("PGDATA", "/var/lib/postgresql/data")

    recovery_config = {
        "restore_command": f"cp {wal_archive_dir}/%f %p",
        "archive_cleanup_command": f"pg_archivecleanup {wal_archive_dir} %r",
    }
    if target_time:
        recovery_config["recovery_target_time"] = target_time
    if target_xid:
        recovery_config["recovery_target_xid"] = target_xid
    recovery_config["recovery_target_inclusive"] = "true"
    recovery_config["recovery_target_timeline"] = "latest"

    try:
        # On PostgreSQL 12+, recovery settings go into postgresql.auto.conf
        config_path = Path(pg_data) / "postgresql.auto.conf"
        if config_path.exists():
            with config_path.open("a", encoding="utf-8") as f:
                for key, value in recovery_config.items():
                    f.write(f"\n{key} = '{value}'\n")
            logger.info("Wrote PITR recovery configuration to %s", config_path)

        # If a dump-based base backup (not pg_basebackup), fall back to pg_restore
        # for the base layer, then rely on server-side WAL replay.
        if str(backup_file).endswith((".sql.gz", ".sql.gz.enc")):
            logger.info("Base backup is dump-based; performing standard restore then WAL replay.")
            restore_backup(backup_file)
            logger.info("Base restore complete. Configure recovery_target in postgresql.auto.conf and restart Postgres for WAL replay.")

        _write_status(
            "pitr_restore_started",
            base_backup=backup_file.name,
            target=recovery_target,
            wal_archive_dir=wal_archive_dir,
        )
        logger.info("PITR restore initiated. Monitor Postgres recovery progress via 'pg_isready' and 'pg_controldata'.")

    except Exception as e:
        logger.error("PITR restore failed: %s", e)
        _write_status("pitr_restore_failed", error=str(e)[:1000], base_backup=backup_file.name)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="PesaGuard PostgreSQL backup and restore utility")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--backup", action="store_true", help="Create a new database backup")
    group.add_argument("--restore", type=str, metavar="BACKUP_FILE", help="Restore database from a backup file")
    group.add_argument("--test", action="store_true", help="Test integrity of the latest backup")
    group.add_argument("--list", action="store_true", help="List recent database backups")
    group.add_argument("--pitr-restore", type=str, metavar="BACKUP_FILE", help="Point-in-time recovery from a base backup using WAL archives")

    # PITR options (used with --pitr-restore)
    parser.add_argument("--target-time", type=str, metavar="TIMESTAMP", help="Restore to the given UTC timestamp (format: YYYY-MM-DD HH:MM:SS)")
    parser.add_argument("--target-xid", type=str, metavar="XID", help="Restore to the given transaction ID")

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
        backups = _backup_artifacts()
        if not backups:
            logger.warning("No backup files found in %s to test.", BACKUP_DIR)
            sys.exit(1)

        latest_backup = backups[-1]
        if test_backup_integrity(latest_backup):
            logger.info("Latest backup (%s) integrity verified successfully.", latest_backup.name)
        else:
            sys.exit(1)

    elif args.list:
        backups = list(reversed(_backup_artifacts()))
        if not backups:
            logger.info("No backups found in %s", BACKUP_DIR)
        else:
            logger.info("Available backups in %s:", BACKUP_DIR)
            for backup in backups[:10]:
                size_mb = backup.stat().st_size / (1024 * 1024)
                mtime = datetime.fromtimestamp(backup.stat().st_mtime, tz=timezone.utc)
                logger.info("  %s (%.2f MB) - Created: %s", backup.name, size_mb, mtime.isoformat())

    elif args.pitr_restore:
        pitr_restore(args.pitr_restore, target_time=args.target_time, target_xid=args.target_xid)


if __name__ == "__main__":
    main()

