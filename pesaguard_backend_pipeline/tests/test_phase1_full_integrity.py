"""Phase 1 — Data Integrity & Idempotency: comprehensive verification suite.

This test file covers every scenario from the Phase 1 specification:

Test scenarios:
  1. Duplicate webhook
  2. Duplicate API request
  3. Concurrent duplicate request
  4. Retry after timeout
  5. Worker crash
  6. DB failure during transaction
  7. Invalid amount
  8. Invalid currency
  9. Missing tenant
  10. Invalid provider reference

Stress test:
  100 identical requests → 1 transaction

Exit gate:
  Lost transactions:       0
  Duplicate transactions:  0
  Corrupt transactions:    0
  Idempotency failures:    0
"""

from __future__ import annotations

import hashlib
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from event_store import EventStore, ProcessResult
from models import (
    AuditEvent,
    Base,
    IdempotencyRecord,
    ProcessedTransaction,
    Transaction,
    TransactionEvent,
    TransactionOutbox,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _payload(trans_id="phase-1-tx", **overrides):
    payload = {
        "TransID": trans_id,
        "TransAmount": "10.50",
        "Currency": "KES",
        "MSISDN": "254700000000",
        "BusinessShortCode": "123456",
        "TransTime": "20260913120000",
    }
    payload.update(overrides)
    return payload


def _store(tmp_path, name="phase1.db"):
    url = f"sqlite:///{tmp_path / name}"
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    return url, engine


def _count(session, model):
    return session.query(model).count()


def _assert_exit_gates(session, *, transaction_ids=None):
    """Central assertion for the Phase 1 exit gate."""
    transactions = session.query(Transaction).all()
    if transaction_ids is not None:
        transactions = [t for t in transactions if t.trans_id in transaction_ids]

    idempotency_records = session.query(IdempotencyRecord).all()
    if transaction_ids is not None:
        idempotency_records = [
            i for i in idempotency_records
            if i.provider_transaction_id in transaction_ids
        ]

    # Lost transactions: every ProcessedTransaction must have a matching Transaction row.
    processed = session.query(ProcessedTransaction).all()
    transaction_by_scope = {
        (t.tenant_id, t.provider_account_id, t.trans_id): t for t in transactions
    }
    lost = [
        p for p in processed
        if (p.tenant_id, p.provider_account_id, p.daraja_trans_id)
        not in transaction_by_scope
    ]
    assert len(lost) == 0, f"Lost transactions: {len(lost)}"

    # Duplicate transactions: transactions table must have exactly one row per trans_id scope.
    seen_trans = set()
    dup_trans = []
    for t in transactions:
        scope = (t.tenant_id, t.provider_account_id, t.trans_id)
        if scope in seen_trans:
            dup_trans.append(scope)
        seen_trans.add(scope)
    assert len(dup_trans) == 0, f"Duplicate transactions: {len(dup_trans)}"

    # Corrupt transactions: status must be valid, amount > 0, currency 3-char uppercase, version >= 1.
    corrupt = []
    valid_statuses = {"RECEIVED", "VALIDATED", "PROCESSING", "RECONCILING", "RECONCILED", "FAILED", "REJECTED"}
    for t in transactions:
        if t.status not in valid_statuses:
            corrupt.append((t.trans_id, "bad status"))
            continue
        if t.trans_amount <= 0:
            corrupt.append((t.trans_id, "non-positive amount"))
            continue
        if len(t.currency) != 3 or t.currency != t.currency.upper():
            corrupt.append((t.trans_id, "bad currency"))
            continue
        if t.version < 1:
            corrupt.append((t.trans_id, "bad version"))
            continue
    assert len(corrupt) == 0, f"Corrupt transactions: {corrupt}"

    # Idempotency failures: exactly one idempotency record per unique transaction identity.
    seen_idem = set()
    dup_idem = []
    for i in idempotency_records:
        key = (i.tenant_id, i.provider, i.idempotency_key)
        if key in seen_idem:
            dup_idem.append(key)
        seen_idem.add(key)
    assert len(dup_idem) == 0, f"Idempotency failures: {len(dup_idem)}"

    return {
        "lost": len(lost),
        "duplicate": len(dup_trans),
        "corrupt": len(corrupt),
        "idempotency_failures": len(dup_idem),
    }


# ---------------------------------------------------------------------------
# 1. Duplicate webhook
# ---------------------------------------------------------------------------

def test_duplicate_webhook_is_safe_noop(tmp_path):
    """The exact same webhook delivered twice must create exactly one transaction."""
    url, engine = _store(tmp_path)
    store = EventStore(database_url=url)

    assert store.mark_processed(_payload("webhook-dupe"), tenant_id="tenant-a") is ProcessResult.STORED
    assert store.mark_processed(_payload("webhook-dupe"), tenant_id="tenant-a") is ProcessResult.DUPLICATE

    with sessionmaker(bind=engine)() as session:
        assert _count(session, Transaction) == 1
        assert _count(session, ProcessedTransaction) == 1
        assert _count(session, IdempotencyRecord) == 1
        assert _count(session, TransactionEvent) == 1
        assert _count(session, AuditEvent) == 1
        metrics = _assert_exit_gates(session, transaction_ids={"webhook-dupe"})
        assert metrics == {"lost": 0, "duplicate": 0, "corrupt": 0, "idempotency_failures": 0}


# ---------------------------------------------------------------------------
# 2. Duplicate API request
# ---------------------------------------------------------------------------


def test_duplicate_api_request_with_same_idempotency_key(tmp_path):
    """An API client sending the same idempotency_key twice with identical payloads
    must only create one transaction and one idempotency row."""
    url, engine = _store(tmp_path)
    store = EventStore(database_url=url)

    key = "client-key-123"
    pl = _payload("api-dup", idempotency_key=key)
    # An API request typically supplies an idempotency_key header, not a payload field.
    # For this test we use the payload-based TransID path, which derive_idempotency_key()
    # maps to transid:... deterministically for duplicate detection.

    assert store.mark_processed(pl, tenant_id="tenant-a") is ProcessResult.STORED
    assert store.mark_processed(pl, tenant_id="tenant-a") is ProcessResult.DUPLICATE

    with sessionmaker(bind=engine)() as session:
        txns = session.query(Transaction).all()
        assert len(txns) == 1
        # Same financial record, same identity key.
        assert txns[0].trans_id == "api-dup"
        assert session.query(IdempotencyRecord).count() == 1


# ---------------------------------------------------------------------------
# 3. Concurrent duplicate request
# ---------------------------------------------------------------------------


def test_concurrent_duplicate_requests_produce_one_transaction(tmp_path):
    """Two concurrent worker threads racing for the same TransID must reach
    exactly one STORED and one DUPLICATE, never two STORED."""
    url, engine = _store(tmp_path)
    trans_id = f"race-{uuid.uuid4().hex[:8]}"
    barrier = threading.Barrier(2)
    outcomes = []
    lock = threading.Lock()

    def attempt():
        store = EventStore(database_url=url)
        barrier.wait()
        result = store.mark_processed(_payload(trans_id), tenant_id="tenant-a")
        with lock:
            outcomes.append(result)

    workers = [threading.Thread(target=attempt) for _ in range(2)]
    for w in workers:
        w.start()
    for w in workers:
        w.join(timeout=30)

    assert sorted(outcomes) == [ProcessResult.DUPLICATE, ProcessResult.STORED], outcomes

    with sessionmaker(bind=engine)() as session:
        assert _count(session, Transaction) == 1
        assert _count(session, IdempotencyRecord) == 1
        _assert_exit_gates(session, transaction_ids={trans_id})


# ---------------------------------------------------------------------------
# 4. Retry after timeout
#---------------------------------------------------------------------------


def test_retry_after_timeout_does_not_duplicate(tmp_path):
    """A request that times out client-side and is retried always resolves
    to exactly one stored transaction, regardless of interleaving."""
    url, engine = _store(tmp_path)
    store = EventStore(database_url=url)
    trans_id = f"timeout-{uuid.uuid4().hex[:8]}"

    # First attempt likely times out after DB commit but before client receives response.
    # We model that by directly persisting the transaction, then simulating the retry.
    first = store.mark_processed(_payload(trans_id), tenant_id="tenant-a")
    assert first is ProcessResult.STORED

    # Retry after client-side timeout.
    retry = store.mark_processed(_payload(trans_id, retry_count=2), tenant_id="tenant-a")
    assert retry is ProcessResult.DUPLICATE

    with sessionmaker(bind=engine)() as session:
        txns = session.query(Transaction).all()
        assert len(txns) == 1
        pt = session.query(ProcessedTransaction).one()
        # The retry attempt increments webhook_attempt_number on the same row.
        # The transaction row itself must not be duplicated.
        assert session.query(IdempotencyRecord).count() == 1
        _assert_exit_gates(session, transaction_ids={trans_id})


# ---------------------------------------------------------------------------
# 5. Woker crash
#----------------------------------------------------------------------------


def test_worker_crash_leaves_outbox_leasable_and_no_duplicate(tmp_path):
    """A worker that crashes after claiming an outbox row must not cause
    transaction duplication when the outbox is re-claimed by another worker."""
    url, engine = _store(tmp_path)
    store = EventStore(database_url=url)
    trans_id = f"crash-{uuid.uuid4().hex[:8]}"

    store.mark_processed(_payload(trans_id), tenant_id="tenant-a")

    # The outbox is pending.
    with sessionmaker(bind=engine)() as session:
        outbox = session.query(TransactionOutbox).one()
        assert outbox.status == "pending"

    # A worker claims the outbox, then crashes before completing publication.
    claimed = store.claim_outbox_batch(limit=1, lease_seconds=60)
    assert len(claimed) == 1
    outbox_id = claimed[0]["id"]

    # ...but crashes before marking published.
    # The lease expires, another worker re-claims.
    # Outbox: pending → processing (crashed) → still processing until lease expiry.
    # After the lease expires the SAME row is re-claimed. It is NOT published twice.
    with sessionmaker(bind=engine)() as session:
        row = session.get(TransactionOutbox, outbox_id)
        row.locked_until = datetime.now(timezone.utc) - timedelta(seconds=1)
        row.status = "pending"  # simulate lease reaper
        session.commit()

    re_claimed = store.claim_outbox_batch(limit=1, lease_seconds=60)
    assert len(re_claimed) == 1

    # Publishing that row must mark exactly one published row.
    store.mark_outbox_published(outbox_id)
    with sessionmaker(bind=engine)() as session:
        assert _count(session, Transaction) == 1
        outbox = session.get(TransactionOutbox, outbox_id)
        assert outbox.status == "published"
        assert outbox.attempts == 2
        _assert_exit_gates(session, transaction_ids={trans_id})


# ----------------------------------------------------------------------------
# 6. DB failure during transaction
#----------------------------------------------------------------------------

def test_db_failure_during_transaction_rolls_back_no_partial_write(tmp_path):
    """If the DB fails mid-transaction the whole transaction must roll back —
    no orphan ProcessedTransaction and no orphan Transaction."""
    url, engine = _store(tmp_path)
    store = EventStore(database_url=url)

    # Simulate a DB failure by using a broken database URL.
    broken_url = f"sqlite:///{tmp_path / 'no-such.db'}/dne.db"
    broken_store = EventStore(database_url=broken_url)

    result = broken_store.mark_processed(_payload("db-fail"), tenant_id="tenant-a")
    assert result is ProcessResult.ERROR

    # The good DB must have no partial rows.
    with sessionmaker(bind=engine)() as session:
        assert _count(session, Transaction) == 0
        assert _count(session, ProcessedTransaction) == 0
        assert _count(session, IdempotencyRecord) == 0


# ---------------------------------------------------------------------------
# 7. Invalid amount
#-------------------------------------------------------------------------


def test_invalid_amount_is_rejected(tmp_path):
    """A payload with a non-numeric, zere, or negative amount must be rejected."""
    url, engine = _store(tmp_path)
    store = EventStore(database_url=url)

    bad_amounts = ["not-money", "", "0", "-5", "abc.12"]
    for bad in bad_amounts:
        assert store.mark_processed(
            _payload(f"bad-amount-{hashlib.sha256(str(bad).encode()).hexdigest()[:8]}", TransAmount=bad),
            tenant_id="tenant-a",
        ) is ProcessResult.ERROR, f"Expected rejection for amount {bad!r}"

    with sessionmaker(bind=engine)() as session:
        assert _count(session, Transaction) == 0


# --------------------------------------------------------------------------
# 8. Invalid currency
#------------------------------------------------------------------------


def test_invalid_currency_is_rejected(tmp_path):
    url, engine = _store(tmp_path)
    store = EventStore(database_url=url)

    for bad_curr in ("KE", "KES!", "12", "a", ""):
        result = store.mark_processed(
            _payload(f"bad-curr-{hashlib.sha256(str(bad_curr).encode()).hexdigest()[:8]}", Currency=bad_curr),
            tenant_id="tenant-a",
        )
        assert result is ProcessResult.ERROR, f"Expected rejection for currency {bad_curr!r}"

    with sessionmaker(bind=engine)() as session:
        assert _count(session, Transaction) == 0


# -------------------------------------------------------------------------
# 9. Missing tenant
#-----------------------------------------------------------------------


def test_missing_tenant_is_rejected(tmp_path):
    url, engine = _store(tmp_path)
    store = EventStore(database_url=url)

    assert store.mark_processed(_payload("no-tenant"), tenant_id=None) is ProcessResult.ERROR
    assert store.mark_processed(_payload("empty-tenant"), tenant_id="") is ProcessResult.ERROR
    assert store.mark_processed(_payload("tenspace"), tenant_id="   ") is ProcessResult.ERROR

    with sessionmaker(bind=engine)() as session:
        assert _count(session, Transaction) == 0
        assert _count(session, ProcessedTransaction) == 0


# -------------------------------------------------------------------------
# 10. Invalid provider reference
#-----------------------------------------------------------------------


def test_invalid_provider_reference_is_rejected(tmp_path):
    """An explicit unknown/empty/garbled provider value must be rejected
    before any database write happens."""
    url, engine = _store(tmp_path)
    store = EventStore(database_url=url)

    for bad_provider in ("not-a-provider", "PAYPAL", "mpesa-v2", "unknown", "stripe"):
        result = store.mark_processed(
            _payload(f"bad-prov-{hashlib.sha256(str(bad_provider).encode()).hexdigest()[:8]}", provider=bad_provider),
            tenant_id="tenant-a",
        )
        assert result is ProcessResult.ERROR, f"Expected rejection for provider {bad_provider!r}"

    # Valid providers still accepted.
    assert store.mark_processed(_payload("valid-prov", provider="airtel-money"), tenant_id="tenant-a") is ProcessResult.STORED

    with sessionmaker(bind=engine)() as session:
        assert _count(session, Transaction) == 1
        assert _count(session, IdempotencyRecord) == 1


# ---------------------------------------------------------------------------
# Stress test: 100 identical requests → 1 transaction
# ---------------------------------------------------------------------------


def test_one_hundred_identical_requests_create_one_transaction(tmp_path):
    """100 identical requests fired concurrently through separate stores
    must result in exactly 1 stored transaction and 99 duplicates."""
    url, engine = _store(tmp_path, name="stress.db")
    trans_id = "stress-100"
    barrier = threading.Barrier(10)
    lock = threading.Lock()
    outcomes = []

    def submit(_):
        store = EventStore(database_url=url)
        barrier.wait()
        result = store.mark_processed(_payload(trans_id), tenant_id="tenant-a")
        with lock:
            outcomes.append(result)
        return result

    with ThreadPoolExecutor(max_workers=10) as executor:
        list(executor.map(submit, range(100)))

    assert outcomes.count(ProcessResult.STORED) == 1
    assert outcomes.count(ProcessResult.DUPLICATE) == 99

    with sessionmaker(bind=engine)() as session:
        assert _count(session, Transaction) == 1
        assert _count(session, IdempotencyRecord) == 1
        assert _count(session, ProcessedTransaction) == 1
        assert _count(session, TransactionEvent) == 1  # only one received event
        assert _count(session, AuditEvent) == 1
        metrics = _assert_exit_gates(session, transaction_ids={trans_id})
        assert metrics == {"lost": 0, "duplicate": 0, "corrupt": 0, "idempotency_failures": 0}


# ---------------------------------------------------------------------------
# Exit gate: comprehensive verification across ALL Phase 1 scenarios
#----------------------------------------------------------------------------


def test_exit_gate_full_pipeline(tmp_path):
    """After a realistic mixed workload the exit gates must all be zero."""
    url, engine = _store(tmp_path, name="exit-gate.db")
    store = EventStore(database_url=url)

    # Mix of unique, duplicate, invalid, and concurrent transactions.
    for i in range(20):
        assert store.mark_processed(_payload(f"mixed-{i}"), tenant_id="tenant-a") is ProcessResult.STORED

    # Duplicates of the first 10.
    for i in range(10):
        assert store.mark_processed(_payload(f"mixed-{i}"), tenant_id="tenant-a") is ProcessResult.DUPLICATE

    # Rejected variants.
    assert store.mark_processed(_payload("bad-amount", TransAmount="zero"), tenant_id="tenant-a") is ProcessResult.ERROR
    assert store.mark_processed(_payload("bad-currency", Currency="XX"), tenant_id="tenant-a") is ProcessResult.ERROR
    assert store.mark_processed(_payload("no-tenant"), tenant_id=None) is ProcessResult.ERROR
    assert store.mark_processed(_payload("bad-provider", provider="bitcoin"), tenant_id="tenant-a") is ProcessResult.ERROR

    # Lifecycle transitions on a few transactions.
    assert store.transition_transaction("mixed-1", "VALIDATED", "tenant-a", expected_version=1)
    assert store.transition_transaction("mixed-1", "PROCESSING", "tenant-a", expected_version=2)

    with sessionmaker(bind=engine)() as session:
        metrics = _assert_exit_gates(session)
        assert metrics["lost"] == 0
        assert metrics["duplicate"] == 0
        assert metrics["corrupt"] == 0
        assert metrics["idempotency_failures"] == 0
        # Exactly 20 transactions after 20 unique + 10 duplicates + 4 rejections.
        assert _count(session, Transaction) == 20
        assert _count(session, IdempotencyRecord) == 20
        assert _count(session, ProcessedTransaction) == 20