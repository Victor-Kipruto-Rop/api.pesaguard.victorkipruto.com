from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from event_store import EventStore, ProcessResult
from lifecycle import InvalidLifecycleTransition, transition_transaction
from models import AuditEvent, Base, IdempotencyRecord, ProcessedTransaction, Transaction, TransactionEvent


def _payload(trans_id="phase-1-tx"):
    return {
        "TransID": trans_id,
        "TransAmount": "10.50",
        "Currency": "KES",
        "MSISDN": "254700000000",
        "BusinessShortCode": "123456",
        "TransTime": "20260913120000",
    }


def _store(tmp_path):
    url = f"sqlite:///{tmp_path / 'phase1.db'}"
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    return url, engine


def test_duplicate_api_retry_has_one_financial_record_and_one_identity(tmp_path):
    url, engine = _store(tmp_path)
    store = EventStore(database_url=url)

    assert store.mark_processed(_payload(), tenant_id="tenant-a") is ProcessResult.STORED
    assert store.mark_processed(_payload(), tenant_id="tenant-a") is ProcessResult.DUPLICATE
    Session = sessionmaker(bind=engine)
    with Session() as session:
        assert session.query(Transaction).count() == 1
        assert session.query(ProcessedTransaction).count() == 1
        assert session.query(IdempotencyRecord).count() == 1
        assert session.query(TransactionEvent).count() == 1
        assert session.query(AuditEvent).count() == 1


def test_missing_tenant_invalid_amount_and_currency_are_rejected(tmp_path):
    url, engine = _store(tmp_path)
    store = EventStore(database_url=url)

    assert store.mark_processed(_payload(), tenant_id=None) is ProcessResult.ERROR
    invalid_amount = _payload("invalid-amount")
    invalid_amount["TransAmount"] = "not-money"
    assert store.mark_processed(invalid_amount, tenant_id="tenant-a") is ProcessResult.ERROR
    invalid_currency = _payload("invalid-currency")
    invalid_currency["Currency"] = "KE"
    assert store.mark_processed(invalid_currency, tenant_id="tenant-a") is ProcessResult.ERROR
    with sessionmaker(bind=engine)() as session:
        assert session.query(Transaction).count() == 0


def test_transaction_lifecycle_and_optimistic_version(tmp_path):
    url, engine = _store(tmp_path)
    store = EventStore(database_url=url)
    assert store.mark_processed(_payload("lifecycle-tx"), tenant_id="tenant-a") is ProcessResult.STORED

    assert store.transition_transaction("lifecycle-tx", "VALIDATED", "tenant-a", 1)
    assert not store.transition_transaction("lifecycle-tx", "PROCESSING", "tenant-a", 1)
    assert store.transition_transaction("lifecycle-tx", "PROCESSING", "tenant-a", 2)
    with sessionmaker(bind=engine)() as session:
        transaction = session.query(Transaction).one()
        assert transaction.status == "PROCESSING"
        assert transaction.version == 3
        assert session.query(TransactionEvent).count() == 3

    try:
        transition_transaction("PROCESSING", "RECEIVED")
    except InvalidLifecycleTransition:
        pass
    else:
        raise AssertionError("lifecycle regression must be rejected")


def test_one_hundred_identical_requests_create_one_transaction(tmp_path):
    url, engine = _store(tmp_path)

    def submit(_):
        return EventStore(database_url=url).mark_processed(_payload("stress-tx"), tenant_id="tenant-a")

    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(submit, range(100)))

    assert results.count(ProcessResult.STORED) == 1
    assert results.count(ProcessResult.DUPLICATE) == 99
    with sessionmaker(bind=engine)() as session:
        assert session.query(Transaction).count() == 1
        assert session.query(IdempotencyRecord).count() == 1