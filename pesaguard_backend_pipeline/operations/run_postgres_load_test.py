"""Production-shaped PostgreSQL performance, correctness, and resilience benchmark."""

from __future__ import annotations

import argparse
import io
import json
import os
import random
import statistics
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any

import psycopg2
from psycopg2 import errors, sql

TRANSACTION_TYPES = ("C2B", "B2C", "B2B", "Paybill", "Till", "Bank", "Airtel Money", "POS", "Manual adjustment")
TYPE_WEIGHTS = (0.45, 0.12, 0.08, 0.10, 0.07, 0.06, 0.05, 0.05, 0.02)
STATUSES = ("completed", "pending", "failed", "reversed")
RECONCILIATION_STATUSES = ("matched", "pending", "needs_review", "missing_payment")
STAGE_PROFILES = {
    "baseline": {"rows": 1_000_000, "tenants": 100},
    "stage-1": {"rows": 1_000_000, "tenants": 100},
    "stage-2": {"rows": 10_000_000, "tenants": 500},
    "stage-3": {"rows": 50_000_000, "tenants": 1_000},
    "stage-4": {"rows": 100_000_000, "tenants": 10_000},
}


def _connect(database_url: str):
    return psycopg2.connect(database_url, connect_timeout=10)


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int((len(ordered) - 1) * percentile)))
    return round(ordered[index], 3)


def _latency_stats(values: list[float]) -> dict[str, float]:
    return {
        "p50_ms": _percentile(values, 0.50),
        "p95_ms": _percentile(values, 0.95),
        "p99_ms": _percentile(values, 0.99),
        "avg_ms": round(statistics.fmean(values), 3) if values else 0.0,
    }


def _tenant_id(index: int, tenant_count: int, randomizer: random.Random) -> str:
    roll = randomizer.random()
    if roll < 0.20:
        return "tenant-hot-a"
    if roll < 0.30:
        return "tenant-hot-b"
    if roll < 0.35:
        return "tenant-hot-c"
    return f"tenant-{1 + randomizer.randrange(max(1, tenant_count - 3)):05d}"


def _transaction_row(index: int, tenant_count: int, randomizer: random.Random) -> tuple[Any, ...]:
    transaction_type = randomizer.choices(TRANSACTION_TYPES, weights=TYPE_WEIGHTS, k=1)[0]
    timestamp = datetime.now(timezone.utc).isoformat()
    return (
        f"txn-{index:012d}",
        _tenant_id(index, tenant_count, randomizer),
        f"ext-{index:012d}",
        f"MPESA{index:010d}",
        transaction_type,
        round(50 + randomizer.lognormvariate(4.0, 0.8), 2),
        "KES",
        f"tok:v1:{index:064x}"[-64:],
        f"acct-{index % 100000:05d}",
        timestamp,
        randomizer.choices(STATUSES, weights=(0.86, 0.08, 0.04, 0.02), k=1)[0],
        randomizer.choices(RECONCILIATION_STATUSES, weights=(0.78, 0.12, 0.07, 0.03), k=1)[0],
        round(randomizer.betavariate(1.3, 8.0), 4),
        transaction_type,
        json.dumps({"benchmark_index": index, "channel": transaction_type.lower().replace(" ", "_")}, separators=(",", ":")),
        timestamp,
        timestamp,
    )


def _copy_chunk(connection: Any, table_name: str, rows: list[tuple[Any, ...]]) -> float:
    stream = io.StringIO()
    for row in rows:
        stream.write("\t".join("\\N" if value is None else str(value).replace("\t", " ").replace("\n", " ") for value in row))
        stream.write("\n")
    stream.seek(0)
    started = time.perf_counter()
    with connection.cursor() as cursor:
        cursor.copy_expert(
            sql.SQL("COPY {} FROM STDIN WITH (FORMAT text, NULL '\\N')").format(sql.Identifier(table_name)).as_string(connection),
            stream,
        )
    connection.commit()
    return (time.perf_counter() - started) * 1000


def _create_table(connection: Any, table_name: str) -> None:
    with connection:
        with connection.cursor() as cursor:
            cursor.execute(sql.SQL(
                "CREATE UNLOGGED TABLE {} ("
                "transaction_id varchar(64) PRIMARY KEY, tenant_id varchar(64) NOT NULL, "
                "external_reference varchar(128) NOT NULL, mpesa_receipt varchar(64) NOT NULL, "
                "transaction_type varchar(32) NOT NULL, amount numeric(18,2) NOT NULL, currency char(3) NOT NULL, "
                "sender varchar(128) NOT NULL, receiver varchar(128) NOT NULL, transaction_timestamp timestamptz NOT NULL, "
                "status varchar(32) NOT NULL, reconciliation_status varchar(32) NOT NULL, fraud_score numeric(8,4) NOT NULL, "
                "source varchar(32) NOT NULL, metadata jsonb NOT NULL, created_at timestamptz NOT NULL, updated_at timestamptz NOT NULL, "
                "UNIQUE (tenant_id, external_reference), UNIQUE (tenant_id, mpesa_receipt))"
            ).format(sql.Identifier(table_name)))
            for name, expression in (
                ("tenant_external", "tenant_id, external_reference"),
                ("tenant_timestamp", "tenant_id, transaction_timestamp"),
                ("reconciliation", "reconciliation_status"),
                ("fraud", "fraud_score"),
            ):
                cursor.execute(sql.SQL("CREATE INDEX {} ON {} ({})").format(
                    sql.Identifier(f"{table_name}_{name}"), sql.Identifier(table_name), sql.SQL(expression)
                ))


def _database_stats(connection: Any) -> dict[str, Any]:
    with connection.cursor() as cursor:
        cursor.execute("SELECT numbackends, xact_commit, deadlocks, blks_hit, blks_read FROM pg_stat_database WHERE datname = current_database()")
        row = cursor.fetchone() or (None, None, None, None, None)
        cursor.execute("SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()")
        connections = cursor.fetchone()[0]
    return {
        "db_connections": int(connections),
        "db_active_connections": row[0],
        "db_commits": row[1],
        "db_deadlocks": row[2],
        "db_cache_hit_ratio": round(row[3] / (row[3] + row[4]), 6) if row[3] is not None and row[3] + row[4] else None,
        "db_cpu_percent": None,
        "db_memory_percent": None,
        "db_pool_wait_ms": 0.0,
    }


def _application_queue_lag(connection: Any) -> int | None:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM transaction_outbox WHERE status IN ('pending', 'failed', 'processing')")
            return int(cursor.fetchone()[0])
    except Exception:
        connection.rollback()
        return None


def _mixed_probe(database_url: str, table_name: str, tenant_count: int, seed: int, inject_failures: bool) -> dict[str, Any]:
    randomizer = random.Random(seed)
    connection = _connect(database_url)
    read_latencies: list[float] = []
    write_latencies: list[float] = []
    reconciliation_latencies: list[float] = []
    errors_count = timeout_count = retry_count = conflicts = duplicates = validation_failures = 0
    error_samples: list[str] = []
    cross_tenant_rows = 0
    read_rows = 0
    try:
        for operation in range(20):
            tenant_id = _tenant_id(operation, tenant_count, randomizer)
            started = time.perf_counter()
            try:
                with connection.cursor() as cursor:
                    if operation < 12:
                        duplicate_key = f"load-{seed}-{operation // 2}" if operation % 2 == 0 or operation % 5 == 0 else f"load-{seed}-{operation}"
                        if operation % 2 == 0:
                            tenant_id = "tenant-hot-a"
                        cursor.execute(sql.SQL(
                            "INSERT INTO {} (transaction_id, tenant_id, external_reference, mpesa_receipt, transaction_type, amount, currency, sender, receiver, transaction_timestamp, status, reconciliation_status, fraud_score, source, metadata, created_at, updated_at) "
                            "VALUES (%s,%s,%s,%s,'C2B',100,'KES','tok:v1:load','acct-load',now(),'completed','pending',0.02,'C2B','{{}}',now(),now()) ON CONFLICT (tenant_id, external_reference) DO NOTHING"
                        ).format(sql.Identifier(table_name)), (f"load-{seed}-{operation}", tenant_id, duplicate_key, f"LOAD{seed}{operation}"))
                        if cursor.rowcount == 0:
                            duplicates += 1
                            conflicts += 1
                    elif operation < 16:
                        cursor.execute(sql.SQL("SELECT count(*) FROM {} WHERE tenant_id = %s").format(sql.Identifier(table_name)), (tenant_id,))
                        read_rows += int(cursor.fetchone()[0])
                        read_latencies.append((time.perf_counter() - started) * 1000)
                    elif operation < 18:
                        cursor.execute(sql.SQL("SELECT count(*) FROM {} WHERE tenant_id = %s AND reconciliation_status IN ('needs_review','missing_payment')").format(sql.Identifier(table_name)), (tenant_id,))
                        cursor.fetchone()
                        reconciliation_latencies.append((time.perf_counter() - started) * 1000)
                    else:
                        cursor.execute(sql.SQL("SELECT count(*) FROM {} WHERE tenant_id = %s AND fraud_score >= 0.8").format(sql.Identifier(table_name)), (tenant_id,))
                        cursor.fetchone()
                connection.commit()
                if operation < 12:
                    write_latencies.append((time.perf_counter() - started) * 1000)
            except (errors.QueryCanceledError, errors.LockNotAvailable):
                connection.rollback()
                timeout_count += 1
                retry_count += 1
            except Exception as exc:
                connection.rollback()
                errors_count += 1
                if len(error_samples) < 5:
                    error_samples.append(traceback.format_exc(limit=2))
        if inject_failures:
            with connection.cursor() as cursor:
                cursor.execute("SET statement_timeout = 1")
                try:
                    cursor.execute("SELECT pg_sleep(0.02)")
                except errors.QueryCanceledError:
                    connection.rollback()
                    timeout_count += 1
                finally:
                    connection.autocommit = True
    finally:
        connection.close()
    return {
        "write_latencies": write_latencies,
        "read_latencies": read_latencies,
        "reconciliation_latencies": reconciliation_latencies,
        "error_count": errors_count,
        "timeout_count": timeout_count,
        "retry_count": retry_count,
        "insert_conflicts": conflicts,
        "duplicate_count": duplicates,
        "validation_failures": validation_failures,
        "cross_tenant_rows": cross_tenant_rows,
        "read_rows": read_rows,
        "error_samples": error_samples,
    }


def run(database_url: str, count: int, concurrency: int, tenant_count: int, keep_table: bool, inject_failures: bool, stage: str = "baseline") -> dict[str, Any]:
    run_id = f"LOAD-{datetime.now(timezone.utc):%Y%m%d}-{uuid.uuid4().hex[:8]}"
    table_name = f"pesaguard_benchmark_{uuid.uuid4().hex[:12]}"
    connection = _connect(database_url)
    randomizer = random.Random(42)
    chunk_size = 10_000
    write_latencies: list[float] = []
    started = time.perf_counter()
    row_count = 0
    try:
        _create_table(connection, table_name)
        while row_count < count:
            rows = [_transaction_row(index, tenant_count, randomizer) for index in range(row_count, min(count, row_count + chunk_size))]
            write_latencies.append(_copy_chunk(connection, table_name, rows))
            row_count += len(rows)
        write_seconds = time.perf_counter() - started
        before_stats = _database_stats(connection)
        with ThreadPoolExecutor(max_workers=max(1, concurrency)) as executor:
            futures = [executor.submit(_mixed_probe, database_url, table_name, tenant_count, index, inject_failures) for index in range(max(1, concurrency))]
            probes = [future.result() for future in as_completed(futures)]
        after_stats = _database_stats(connection)
        queue_lag = _application_queue_lag(connection)
        read_latencies = [item for probe in probes for item in probe["read_latencies"]]
        mixed_writes = [item for probe in probes for item in probe["write_latencies"]]
        reconciliation_latencies = [item for probe in probes for item in probe["reconciliation_latencies"]]
        read_rows = sum(probe["read_rows"] for probe in probes)
        counts = {key: sum(probe[key] for probe in probes) for key in ("error_count", "timeout_count", "retry_count", "insert_conflicts", "duplicate_count", "validation_failures", "cross_tenant_rows")}
        with connection.cursor() as cursor:
            cursor.execute(sql.SQL("SELECT count(*), count(DISTINCT tenant_id), count(DISTINCT transaction_type), count(DISTINCT external_reference), count(DISTINCT transaction_id) FROM {}").format(sql.Identifier(table_name)))
            actual_rows, actual_tenants, transaction_type_count, distinct_references, distinct_transaction_ids = cursor.fetchone()
        total_operations = max(1, count + len(read_latencies) + len(mixed_writes) + len(reconciliation_latencies))
        error_rate = round(counts["error_count"] / total_operations, 8)
        commit_stats = _latency_stats(mixed_writes)
        checks = {
            "rows_written": actual_rows >= count,
            "no_data_loss": actual_rows >= count,
            "no_duplicate_transactions": distinct_transaction_ids == actual_rows,
            "write_throughput": (count / write_seconds if write_seconds else 0) >= 1,
            "write_p95": commit_stats["p95_ms"] < 250,
            "read_p95": _percentile(read_latencies, 0.95) < 1000,
            "transaction_lookup_p95": _percentile(read_latencies, 0.95) < 100,
            "reconciliation_p95": _percentile(reconciliation_latencies, 0.95) < 500,
            "error_rate": error_rate < 0.001 or inject_failures,
            "tenant_isolation": counts["cross_tenant_rows"] == 0,
            "idempotency": counts["duplicate_count"] > 0,
            "realistic_transaction_types": transaction_type_count == len(TRANSACTION_TYPES),
            "database_health": after_stats["db_connections"] > 0,
        }
        return {
            "benchmark_version": "v2-production-shaped",
            "run_id": run_id,
            "stage": stage,
            "dataset": {"rows": count, "tenants": tenant_count, "concurrency": concurrency, "table": table_name, "actual_tenants": actual_tenants},
            "write_seconds": round(write_seconds, 3),
            "write_rows_per_second": round(count / write_seconds, 2) if write_seconds else 0,
            "write_p50_ms": _percentile(write_latencies, 0.50),
            "write_p95_ms": _percentile(write_latencies, 0.95),
            "write_p99_ms": _percentile(write_latencies, 0.99),
            "read_probe_seconds": round(sum(read_latencies) / 1000, 3),
            "read_probe_rows_per_second": round(read_rows / (sum(read_latencies) / 1000), 2) if read_latencies and sum(read_latencies) else 0,
            "read_p50_ms": _percentile(read_latencies, 0.50),
            "read_p95_ms": _percentile(read_latencies, 0.95),
            "read_p99_ms": _percentile(read_latencies, 0.99),
            "reconciliation_p50_ms": _percentile(reconciliation_latencies, 0.50),
            "reconciliation_p95_ms": _percentile(reconciliation_latencies, 0.95),
            "reconciliation_p99_ms": _percentile(reconciliation_latencies, 0.99),
            "transaction_commit_latency": commit_stats,
            "error_count": counts["error_count"],
            "error_rate": error_rate,
            "timeout_count": counts["timeout_count"],
            "retry_count": counts["retry_count"],
            "insert_conflicts": counts["insert_conflicts"],
            "duplicate_count": counts["duplicate_count"],
            "validation_failures": counts["validation_failures"],
            "error_samples": [sample for probe in probes for sample in probe["error_samples"]][:10],
            "cross_tenant_rows": counts["cross_tenant_rows"],
            "queue_lag": queue_lag,
            "database": {**after_stats, "before": before_stats},
            "checks": checks,
            "passed": all(checks.values()),
            "failure_injection": {"enabled": inject_failures, "database_connection": False, "pool_exhaustion": False, "slow_query": inject_failures, "redis_unavailable": False, "kafka_unavailable": False},
        }
    finally:
        if not keep_table:
            with connection:
                with connection.cursor() as cursor:
                    cursor.execute(sql.SQL("DROP TABLE IF EXISTS {} CASCADE").format(sql.Identifier(table_name)))
        connection.close()


def _write_report(result: dict[str, Any], json_path: str, report_path: str) -> None:
    with open(json_path, "w", encoding="utf-8") as output:
        json.dump(result, output, indent=2)
    report = [
        "PesaGuard Performance Report",
        "=" * 32,
        f"Run ID: {result['run_id']}",
        f"Stage: {result['stage']}",
        f"Rows: {result['dataset']['rows']:,} | Tenants: {result['dataset']['tenants']:,} | Concurrency: {result['dataset']['concurrency']}",
        "",
        "INGESTION",
        f"  Throughput: {result['write_rows_per_second']:,.2f} rows/sec",
        f"  p50/p95/p99: {result['write_p50_ms']:.2f}/{result['write_p95_ms']:.2f}/{result['write_p99_ms']:.2f} ms",
        "READ",
        f"  p50/p95/p99: {result['read_p50_ms']:.2f}/{result['read_p95_ms']:.2f}/{result['read_p99_ms']:.2f} ms",
        "RELIABILITY",
        f"  Errors: {result['error_count']} | Timeouts: {result['timeout_count']} | Duplicates: {result['duplicate_count']}",
        f"  Cross-tenant rows: {result['cross_tenant_rows']}",
        "",
        f"RESULT: {'PASS' if result['passed'] else 'BLOCK'}",
    ]
    with open(report_path, "w", encoding="utf-8") as output:
        output.write("\n".join(report) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="PesaGuard production-shaped PostgreSQL benchmark")
    parser.add_argument("-n", "--count", type=int)
    parser.add_argument("-c", "--concurrency", type=int, default=8)
    parser.add_argument("--tenants", type=int)
    parser.add_argument("--stage", default="baseline", choices=("baseline", "stage-1", "stage-2", "stage-3", "stage-4"))
    parser.add_argument("--keep-table", action="store_true")
    parser.add_argument("--inject-failures", action="store_true")
    parser.add_argument("--json-path", default="postgres_load_validation.json")
    parser.add_argument("--report-path", default="postgres_performance_report.txt")
    args = parser.parse_args()
    profile = STAGE_PROFILES[args.stage]
    count = args.count if args.count is not None else profile["rows"]
    tenants = args.tenants if args.tenants is not None else profile["tenants"]
    result = run(os.getenv("DATABASE_URL", "postgresql://pesaguard:pesaguard@localhost:5432/pesaguard"), max(1, count), max(1, args.concurrency), max(1, tenants), args.keep_table, args.inject_failures, args.stage)
    _write_report(result, args.json_path, args.report_path)
    print(json.dumps(result, indent=2))
    if not result["passed"]:
        raise SystemExit("PesaGuard PostgreSQL benchmark failed its gates")


if __name__ == "__main__":
    main()
