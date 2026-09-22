import pytest

from app_2 import app
from test_config import configure_test_database

configure_test_database()


@pytest.fixture
def client():
    app.config.update(TESTING=True)
    with app.test_client() as test_client:
        yield test_client


def test_export_requires_tenant_scope(client):
    response = client.get("/v1/export/csv")
    assert response.status_code in {400, 401}
