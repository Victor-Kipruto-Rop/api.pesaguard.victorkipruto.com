import os
import sys
import tempfile
from contextlib import suppress

# Tests must never inherit credentials or service endpoints from deployment files.
os.environ["PYTHON_DOTENV_DISABLED"] = "1"
os.environ.setdefault("PESAGUARD_API_URL", "http://localhost:5001")

TESTS_DIR = os.path.dirname(__file__)
PACKAGE_DIR = os.path.dirname(TESTS_DIR)
REPOSITORY_ROOT = os.path.dirname(PACKAGE_DIR)

for path in (REPOSITORY_ROOT, PACKAGE_DIR):
    if path not in sys.path:
        sys.path.insert(0, path)

if len(os.environ.get("JWT_SECRET_KEY", "").encode("utf-8")) < 32:
    os.environ["JWT_SECRET_KEY"] = "test-secret-key-with-at-least-32-bytes"
test_db_path = os.path.join(tempfile.gettempdir(), "pesaguard-test.sqlite3")
if os.path.exists(test_db_path):
    with suppress(PermissionError):
        os.remove(test_db_path)
os.environ.setdefault("PYTEST_TEST_DB_URL", f"sqlite:///{test_db_path}")

from test_config import configure_test_database  # noqa: E402


configure_test_database()

from app_4_advanced_features import engine  # noqa: E402
from auth_rbac import _RevocationBase  # noqa: E402
from models import Base  # noqa: E402


Base.metadata.create_all(engine)
_RevocationBase.metadata.create_all(engine)
