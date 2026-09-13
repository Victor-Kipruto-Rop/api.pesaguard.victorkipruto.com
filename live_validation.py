import json
import os
import sys
import time
import uuid
from pathlib import Path

root = Path(__file__).resolve().parent
os.environ['PYTHONPATH'] = str(root) + os.pathsep + os.environ.get('PYTHONPATH', '')

log_path = root / 'live_validation_output.txt'

try:
    from kafka import KafkaProducer, KafkaConsumer
    from kafka.admin import KafkaAdminClient, NewTopic
    from kafka.structs import TopicPartition
    kafka_ok = True
    kafka_version = __import__('kafka').__version__
except Exception as exc:
    kafka_ok = False
    kafka_version = f'ERROR:{type(exc).__name__}:{exc}'

try:
    import redis
    import psycopg2
    redis_ok = True
    redis_version = redis.__version__
    psycopg_ok = True
except Exception as exc:
    redis_ok = False
    redis_version = f'ERROR:{type(exc).__name__}:{exc}'
    psycopg_ok = False

bootstrap = 'localhost:9092'
producer = None
consumer = None
kafka_smoke = {'ok': False, 'details': 'not run'}

try:
    topic = f'pesaguard.validation.{uuid.uuid4().hex}'
    admin = KafkaAdminClient(bootstrap_servers=[bootstrap], client_id='pesaguard-live-validation')
    admin.create_topics([NewTopic(topic, num_partitions=1, replication_factor=1)])
    admin.close()

    producer = KafkaProducer(
        bootstrap_servers=[bootstrap],
        value_serializer=lambda v: json.dumps(v).encode('utf-8'),
        api_version=(3, 6, 0),
    )
    record = {'id': uuid.uuid4().hex, 'value': 'live-validation'}
    metadata = producer.send(topic, record).get(timeout=10)
    producer.flush()

    consumer = KafkaConsumer(
        bootstrap_servers=[bootstrap],
        value_deserializer=lambda v: json.loads(v.decode('utf-8')),
        api_version=(3, 6, 0),
        enable_auto_commit=False,
    )
    partition = TopicPartition(metadata.topic, metadata.partition)
    consumer.assign([partition])
    consumer.seek(partition, metadata.offset)
    messages = consumer.poll(timeout_ms=10000, max_records=10)
    items = [m.value for batches in messages.values() for m in batches]
    kafka_smoke = {
        'ok': bool(items and items[0] == record),
        'details': items[:3] if items else [],
        'topic': topic,
        'partition': metadata.partition,
        'offset': metadata.offset,
    }
    if not items:
        raise RuntimeError('No Kafka messages received')
except Exception as exc:
    kafka_smoke = {'ok': False, 'details': f'{type(exc).__name__}: {exc}'}
finally:
    if consumer is not None:
        consumer.close()
    if producer is not None:
        producer.close()

try:
    sys.path.insert(0, str(root / 'pesaguard_backend_pipeline'))
    sys.path.insert(0, str(root))
    import reconciliation_engine  # type: ignore[import-not-found]
    import importlib
    module = importlib.import_module('reconciliation_engine')
    engine_ok = hasattr(module, 'evaluate_transaction')
    engine_version = 'loaded'
except Exception as exc:
    engine_ok = False
    engine_version = f'ERROR:{type(exc).__name__}:{exc}'

try:
    sys.path.insert(0, str(root / 'pesaguard_backend_pipeline' / 'operations'))
    from run_load_test import main  # type: ignore[import-not-found]
    fs = {"count": 5000, "threads": 4, "json": True}
    # run the load harness directly via CLI arguments via argv to avoid shell quoting issues
    original_argv = sys.argv[:]
    try:
        sys.argv = ['run_load_test.py', '-n', '5000', '-t', '4', '--json']
        main()
        load_ok = True
        load_details = 'main() completed successfully'
    except Exception as exc:
        load_ok = False
        load_details = f'{type(exc).__name__}: {exc}'
    finally:
        sys.argv = original_argv
except Exception as exc:
    load_ok = False
    load_details = f'{type(exc).__name__}: {exc}'

result = {
    'python_executable': sys.executable,
    'kafka': {'ok': kafka_ok, 'version': kafka_version, 'smoke': kafka_smoke},
    'redis': {'ok': redis_ok, 'version': redis_version},
    'psycopg2': {'ok': psycopg_ok},
    'engine_import': {'ok': engine_ok, 'version': engine_version},
    'load_harness': {'ok': load_ok, 'details': load_details},
}

log_path.write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result, indent=2))
