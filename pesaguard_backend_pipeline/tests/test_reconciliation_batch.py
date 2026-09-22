from types import SimpleNamespace

import reconciliation_job


def test_polled_batch_preserves_partition_order_and_bounds_batch(monkeypatch):
    seen = []

    def fake_process(event, consumer, producer, registry):
        seen.append(event["id"])

    monkeypatch.setattr(reconciliation_job, "_process_message", fake_process)
    messages = {
        "partition-a": [SimpleNamespace(value={"id": index}) for index in range(3)],
        "partition-b": [SimpleNamespace(value={"id": index + 10}) for index in range(2)],
    }
    result = reconciliation_job.process_polled_batch(messages, None, None, None)

    assert result == {"processed": 5, "failed": 0}
    assert seen == [0, 1, 2, 10, 11]


def test_polled_batch_counts_failures_and_commits_only_successes(monkeypatch):
    committed = []

    def fake_process(event, consumer, producer, registry):
        return event["ok"]

    monkeypatch.setattr(reconciliation_job, "_process_message", fake_process)
    monkeypatch.setattr(reconciliation_job, "_commit_message", lambda consumer, message: committed.append(message.offset))
    messages = {"partition-a": [
        SimpleNamespace(value={"ok": True}, offset=7),
        SimpleNamespace(value={"ok": False}, offset=8),
    ]}

    assert reconciliation_job.process_polled_batch(messages, None, None, None) == {"processed": 1, "failed": 1}
    assert committed == [7]
