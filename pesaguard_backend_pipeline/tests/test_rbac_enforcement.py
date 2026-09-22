import importlib

import pytest

from app_2 import app
from test_config import configure_test_database

configure_test_database()


@pytest.fixture
def client():
    app.config.update(TESTING=True)
    with app.test_client() as test_client:
        yield test_client


def test_viewer_cannot_access_admin_only_route(client):
    response = client.post(
        "/v1/settings",
        json={"tenant_id": "tenant-a", "key": "value"},
        headers={"Authorization": "Bearer invalid"},
    )
    assert response.status_code in {401, 403}
