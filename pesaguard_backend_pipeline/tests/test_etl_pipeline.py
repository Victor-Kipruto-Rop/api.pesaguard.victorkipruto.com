from etl_pipeline import ELTPipeline, ETLPipeline, RawDatasetLoader
from event_store import ProcessResult
from ingestion import IngestionService


class FakeEventStore:
    def mark_processed(self, payload, *, tenant_id, idempotency_key_override):
        return ProcessResult.STORED


def test_etl_transforms_and_loads_from_immutable_raw_dataset(tmp_path):
    loader = RawDatasetLoader()
    loader.storage.root = tmp_path / "objects"
    dataset = loader.load(
        tenant_id="tenant-a",
        dataset_id="dataset-1",
        filename="bank.csv",
        content=b'transaction_id,amount,account_id\nbank-1,"1,500",acct-1\n',
    )
    service = IngestionService(FakeEventStore())
    results = ETLPipeline(loader, service).run(dataset, source="bank")
    assert len(results) == 1
    assert results[0].envelope.canonical.amount == "1500.00"
    assert loader.read(dataset) == b'transaction_id,amount,account_id\nbank-1,"1,500",acct-1\n'


def test_elt_transforms_loaded_raw_records_without_mutating_object(tmp_path):
    loader = RawDatasetLoader()
    loader.storage.root = tmp_path / "objects"
    dataset = loader.load(
        tenant_id="tenant-a",
        dataset_id="dataset-2",
        filename="records.json",
        content=b'[{"transaction_id":"tx-1","amount":"10"}]',
    )
    transformed = list(ELTPipeline(loader).transform_loaded(dataset, lambda row: {**row, "source": "analytics"}))
    assert transformed == [{"transaction_id": "tx-1", "amount": "10", "source": "analytics"}]
    assert loader.read(dataset) == b'[{"transaction_id":"tx-1","amount":"10"}]'