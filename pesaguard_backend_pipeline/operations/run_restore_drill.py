"""Restore a backup into an isolated database and verify sentinel queries."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path


def run(backup: Path, target_database_url: str, sentinel_sql: str) -> dict[str, object]:
    if not backup.exists():
        raise FileNotFoundError(backup)
    command = ["python", "pesaguard_backend_pipeline/backup_postgres.py", "--restore", str(backup)]
    env = os.environ.copy()
    env["DATABASE_URL"] = target_database_url
    restore = subprocess.run(command, env=env, capture_output=True, text=True, check=False)
    result: dict[str, object] = {
        "backup": str(backup),
        "target_database": target_database_url.rsplit("/", 1)[-1],
        "restore_returncode": restore.returncode,
        "restore_stderr": restore.stderr[-2000:],
        "sentinel_sql": sentinel_sql,
    }
    if restore.returncode != 0:
        result["passed"] = False
        return result
    verify = subprocess.run(
        ["psql", target_database_url, "-v", "ON_ERROR_STOP=1", "-tAc", sentinel_sql],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    result["sentinel_returncode"] = verify.returncode
    result["sentinel_output"] = verify.stdout.strip()
    result["sentinel_stderr"] = verify.stderr[-2000:]
    result["passed"] = verify.returncode == 0
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="PesaGuard isolated PostgreSQL restore drill")
    parser.add_argument("backup", type=Path)
    parser.add_argument("--target-database-url", required=True)
    parser.add_argument("--sentinel-sql", default="SELECT current_database(), current_schema()")
    parser.add_argument("--json-path", default="restore_drill_result.json")
    args = parser.parse_args()
    result = run(args.backup, args.target_database_url, args.sentinel_sql)
    Path(args.json_path).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()