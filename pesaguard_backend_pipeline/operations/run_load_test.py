"""
High-Performance Load-Test Harness for the PesaGuard Reconciliation Engine.

Simulates high-throughput M-Pesa webhook bursts, evaluating transaction matching performance,
latency percentiles, and multi-threaded throughput.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

try:
    from pesaguard_backend_pipeline.reconciliation_engine import evaluate_transaction
except ImportError:  # pragma: no cover - repo-root invocation fallback
    backend_root = Path(__file__).resolve().parents[1]
    if str(backend_root) not in sys.path:
        sys.path.insert(0, str(backend_root))
    from reconciliation_engine import evaluate_transaction


def generate_mock_event_pair(index: int, force_anomaly: str | None = None) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Generate a realistic M-Pesa event and corresponding internal ledger candidates."""
    trans_id = f"LOAD-{index:07d}"
    phone_suffix = f"{index % 10000:04d}"
    phone = f"2547000{phone_suffix}"
    amount = 100.0 + float(index % 50)

    event = {
        "TransID": trans_id,
        "TransAmount": str(amount),
        "MSISDN": phone,
        "TransTime": "20260726120000",
        "BusinessShortCode": "600000",
    }

    if force_anomaly == "missing_record":
        return event, []

    internal_amount = amount
    internal_phone = phone

    if force_anomaly == "amount_mismatch":
        internal_amount += 15.0  # Trigger needs_review / partial match
    elif force_anomaly == "phone_mismatch":
        internal_phone = "254711111111"

    internal_record = {
        "internal_ref": f"ORD-{index:07d}",
        "amount": internal_amount,
        "phone_number": internal_phone,
        "timestamp": "2026-07-26T12:00:00Z",
        "status": "pending",
    }

    return event, [internal_record]


def run_benchmark_worker(
    batch_indices: List[int],
    seen_trans_ids: Set[str],
    window_minutes: int,
) -> List[Tuple[float, str]]:
    """Execute evaluation batch for a single worker thread, returning (latency_sec, status)."""
    results: List[Tuple[float, str]] = []

    for idx in batch_indices:
        # Inject randomized anomalies (10% missing, 10% amount discrepancy)
        force_anomaly = None
        if idx % 10 == 0:
            force_anomaly = "missing_record"
        elif idx % 15 == 0:
            force_anomaly = "amount_mismatch"

        event, internal_records = generate_mock_event_pair(idx, force_anomaly=force_anomaly)

        start_time = time.perf_counter()
        outcome = evaluate_transaction(
            event=event,
            internal_records=internal_records,
            seen_trans_ids=seen_trans_ids,
            window_minutes=window_minutes,
        )
        elapsed = time.perf_counter() - start_time

        results.append((elapsed, outcome.get("status", "unknown")))

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="PesaGuard Reconciliation Engine Load Test Harness")
    parser.add_argument("-n", "--count", type=int, default=1000, help="Total transaction events to simulate (default: 1000)")
    parser.add_argument("-t", "--threads", type=int, default=4, help="Number of concurrent worker threads (default: 4)")
    parser.add_argument("-w", "--window", type=int, default=15, help="Reconciliation matching window in minutes (default: 15)")
    parser.add_argument("--json", action="store_true", help="Output results telemetry as JSON")
    args = parser.parse_args()

    count = args.count
    num_threads = max(1, args.threads)
    window_minutes = args.window

    if not args.json:
        print(f"Starting load test: {count:,} events across {num_threads} worker threads...")

    seen_trans_ids: Set[str] = set()

    # Partition workload across threads
    chunk_size = (count + num_threads - 1) // num_threads
    chunks = [list(range(i, min(i + chunk_size, count))) for i in range(0, count, chunk_size)]

    overall_start = time.perf_counter()
    all_latencies: List[float] = []
    status_counts: Dict[str, int] = {}

    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [
            executor.submit(run_benchmark_worker, chunk, seen_trans_ids, window_minutes)
            for chunk in chunks
        ]

        for future in as_completed(futures):
            worker_results = future.result()
            for latency, status in worker_results:
                all_latencies.append(latency)
                status_counts[status] = status_counts.get(status, 0) + 1

    total_time = time.perf_counter() - overall_start
    throughput = count / total_time if total_time > 0 else 0.0

    all_latencies.sort()
    p50 = all_latencies[int(len(all_latencies) * 0.50)] * 1000 if all_latencies else 0
    p95 = all_latencies[int(len(all_latencies) * 0.95)] * 1000 if all_latencies else 0
    p99 = all_latencies[int(len(all_latencies) * 0.99)] * 1000 if all_latencies else 0
    avg_lat = (sum(all_latencies) / len(all_latencies)) * 1000 if all_latencies else 0

    metrics = {
        "total_events": count,
        "threads": num_threads,
        "total_duration_sec": round(total_time, 4),
        "throughput_events_per_sec": round(throughput, 2),
        "latency_ms": {
            "avg": round(avg_lat, 3),
            "p50": round(p50, 3),
            "p95": round(p95, 3),
            "p99": round(p99, 3),
        },
        "status_breakdown": status_counts,
    }

    if args.json:
        print(json.dumps(metrics, indent=2))
    else:
        print("\n=== PesaGuard Load Test Summary ===")
        print(f"Total Processed : {count:,} events")
        print(f"Total Duration  : {total_time:.3f} seconds")
        print(f"Throughput      : {throughput:,.2f} ops/sec")
        print(f"Avg Latency     : {avg_lat:.3f} ms")
        print(f"P50 Latency     : {p50:.3f} ms")
        print(f"P95 Latency     : {p95:.3f} ms")
        print(f"P99 Latency     : {p99:.3f} ms")
        print("\nStatus Breakdown:")
        for status, cnt in status_counts.items():
            print(f"  - {status:18s}: {cnt:,} ({cnt / count * 100:.1f}%)")


if __name__ == "__main__":
    main()
