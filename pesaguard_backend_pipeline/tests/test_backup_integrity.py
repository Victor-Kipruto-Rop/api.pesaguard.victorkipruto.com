from pathlib import Path

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
