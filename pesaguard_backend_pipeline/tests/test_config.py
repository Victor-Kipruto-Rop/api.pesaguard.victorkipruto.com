import os

DEFAULT_USE_IN_MEMORY_DB = True
DEFAULT_IN_MEMORY_DB_URL = "sqlite:///:memory:"


def should_use_in_memory_db() -> bool:
    """Return whether tests should default to an in-memory SQLite database."""
    explicit_value = os.getenv("USE_IN_MEMORY_TEST_DB")
    if explicit_value is not None:
        return explicit_value.strip().lower() not in {"0", "false", "no"}

    return DEFAULT_USE_IN_MEMORY_DB


def configure_test_database() -> str:
    """Set DATABASE_URL for tests, optionally using an in-memory SQLite database."""
    db_url = os.getenv("PYTEST_TEST_DB_URL") or os.getenv("TEST_DATABASE_URL")
    if db_url:
        os.environ["DATABASE_URL"] = db_url
        return db_url

    if should_use_in_memory_db():
        os.environ["DATABASE_URL"] = DEFAULT_IN_MEMORY_DB_URL
        return DEFAULT_IN_MEMORY_DB_URL

    return os.environ.get("DATABASE_URL", DEFAULT_IN_MEMORY_DB_URL)
