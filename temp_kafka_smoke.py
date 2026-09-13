import json
import uuid
from kafka import KafkaProducer, KafkaConsumer
from kafka.admin import KafkaAdminClient, NewTopic
from kafka.structs import TopicPartition

bootstrap = 'localhost:9092'
topic = f'pesaguard.validation.{uuid.uuid4().hex}'
admin = KafkaAdminClient(bootstrap_servers=[bootstrap], client_id='pesaguard-smoke')
admin.create_topics([NewTopic(topic, num_partitions=1, replication_factor=1)])
admin.close()

producer = KafkaProducer(
    bootstrap_servers=[bootstrap],
    value_serializer=lambda v: json.dumps(v).encode('utf-8'),
)
consumer = KafkaConsumer(
    bootstrap_servers=[bootstrap],
    enable_auto_commit=False,
    value_deserializer=lambda v: json.loads(v.decode('utf-8')),
)

for i in range(20):
    metadata = producer.send(topic, {'id': i, 'value': f'v{i}'}).get(timeout=10)
producer.flush()
partition = TopicPartition(metadata.topic, metadata.partition)
consumer.assign([partition])
consumer.seek(partition, 0)
msgs = consumer.poll(timeout_ms=10000, max_records=20)
items = [m.value for batches in msgs.values() for m in batches]
if len(items) != 20:
    raise RuntimeError(f'Expected 20 Kafka messages, received {len(items)}')
print('KAFKA_SMOKE', len(items), items[0])
consumer.close()
producer.close()
