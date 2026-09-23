"""Restore one backup into an isolated PostgreSQL target and validate it."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from pesaguard_backend_pipeline.operations import validate_restore


def run_restore_drill(backup_file: Path, database_url: str, output: Path) -> dict[str, object]:
    """Restore and validate a backup without touching the production database."""
    started = time.monotonic()
    result: dict[str, object] = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "backup_file": str(backup_file),
        "database_url_host": database_url.rsplit("@", 1)[-1],
        "status": "failed",
    }
    if not backup_file.is_file():
        result["error"] = "backup file does not exist"
    else:
        environment = os.environ.copy()
        environment["DATABASE_URL"] = database_url
        command = [sys.executable, str(Path(__file__).parents[1] / "backup_postgres.py"), "--restore", str(backup_file)]
        restored = subprocess.run(command, env=environment, capture_output=True, text=True, check=False)
        if restored.returncode != 0:
            result["error"] = restored.stderr[-2000:] or "restore command failed"
        else:
            validation = validate_restore.validate(database_url)
            result["validation"] = validation
            result["status"] = "passed" if validation["status"] == "passed" else "failed"
    result["duration_seconds"] = round(time.monotonic() - started, 3)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup-file", type=Path, required=True)
    parser.add_argument("--database-url", default=os.getenv("RESTORE_DATABASE_URL", ""))
    parser.add_argument("--output", type=Path, default=Path("restore-drill.json"))
    args = parser.parse_args()
    if not args.database_url:
        parser.error("--database-url or RESTORE_DATABASE_URL is required")
    result = run_restore_drill(args.backup_file, args.database_url, args.output)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())