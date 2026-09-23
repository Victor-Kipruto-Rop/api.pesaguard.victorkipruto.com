import json
from pathlib import Path


def test_authoritative_openapi_contract_covers_required_domains():
    spec = json.loads((Path(__file__).parents[2] / "docs" / "api" / "openapi.json").read_text(encoding="utf-8"))

    assert spec["openapi"] == "3.0.3"
    assert spec["info"]["version"] == "1.0.0"
    for path in (
        "/transactions",
        "/transactions/{transaction_id}",
        "/transactions/search",
        "/reconciliation/requests",
        "/reconciliation/{transaction_id}",
        "/fraud/analyse",
        "/fraud/{transaction_id}",
        "/auth/login",
        "/auth/refresh",
    ):
        assert path in spec["paths"]
    assert "IdempotencyKey" in spec["components"]["parameters"]
    assert "Retry-After" in spec["components"]["responses"]["RateLimited"]["headers"]
    assert "Error" in spec["components"]["schemas"]