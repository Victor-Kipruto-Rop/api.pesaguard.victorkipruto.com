"""Opt-in PostgreSQL race coverage for tenant/provider idempotency constraints."""

from __future__ import annotations

import os
import threading
import uuid

import pytest

psycopg2 = pytest.importorskip("psycopg2")


@pytest.mark.skipif(
    os.getenv("PESAGUARD_RUN_POSTGRES_INTEGRATION") != "1"
    or not os.getenv("PESAGUARD_POSTGRES_TEST_URL", "").startswith(("postgresql://", "postgres://")),
    reason="set PESAGUARD_RUN_POSTGRES_INTEGRATION=1 and PESAGUARD_POSTGRES_TEST_URL",
)
def test_concurrent_same_transaction_has_one_winner():
    database_url = os.environ["PESAGUARD_POSTGRES_TEST_URL"]
    trans_id = f"concurrency-{uuid.uuid4().hex}"
    barrier = threading.Barrier(2)
    outcomes: list[str] = []
    lock = threading.Lock()

    def attempt() -> None:
        connection = psycopg2.connect(database_url)
        try:
            with connection:
                with connection.cursor() as cursor:
                    barrier.wait(timeout=10)
                    cursor.execute(
                        "INSERT INTO transactions "
                        "(id, trans_id, tenant_id, provider_account_id, trans_amount, msisdn, "
                        "business_short_code, trans_time, raw_payload) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                        (f"txn_{uuid.uuid4().hex}", trans_id, "tenant-race", "provider-race", "10.00", "tok:v1:test", "600000", "20260913120000", "{}"),
                    )
                    with lock:
                        outcomes.append("stored")
        except psycopg2.errors.UniqueViolation:
            connection.rollback()
            with lock:
                outcomes.append("duplicate")
        finally:
            connection.close()

    workers = [threading.Thread(target=attempt) for _ in range(2)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=20)

    cleanup = psycopg2.connect(database_url)
    try:
        with cleanup:
            with cleanup.cursor() as cursor:
                cursor.execute("DELETE FROM transactions WHERE trans_id = %s", (trans_id,))
    finally:
        cleanup.close()

    assert sorted(outcomes) == ["duplicate", "stored"]
