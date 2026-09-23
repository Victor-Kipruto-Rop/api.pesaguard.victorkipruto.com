from pathlib import Path

import pytest

from pesaguard_backend_pipeline import backup_postgres


def test_backup_manifest_detects_tampering(tmp_path: Path):
    artifact = tmp_path / "pesaguard_20260913_120000.sql.gz"
    artifact.write_bytes(b"-- PostgreSQL database dump\nCREATE TABLE sentinel (id integer);\n")

    backup_postgres._write_manifest(artifact)
    assert backup_postgres._verify_manifest(artifact) is True

    artifact.write_bytes(artifact.read_bytes() + b"tampered")
    assert backup_postgres._verify_manifest(artifact) is False


def test_backup_manifest_is_optional_for_legacy_artifacts(tmp_path: Path):
    artifact = tmp_path / "legacy.sql.gz"
    artifact.write_bytes(b"legacy backup")

    assert backup_postgres._verify_manifest(artifact) is True


def test_pitr_rejects_sql_dump_archives(tmp_path: Path, monkeypatch):
    artifact = tmp_path / "pesaguard_20260923_120000.sql.gz"
    artifact.write_bytes(b"not a base backup")
    status_file = tmp_path / "status.json"
    monkeypatch.setattr(backup_postgres, "STATUS_FILE", status_file)

    with pytest.raises(SystemExit):
        backup_postgres.pitr_restore(artifact, target_time="2026-09-23 12:00:00")

    assert "cannot be used for WAL replay" in status_file.read_text(encoding="utf-8")
