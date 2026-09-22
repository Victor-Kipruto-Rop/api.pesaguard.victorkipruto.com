from realtime_worker import STAGES
from topics import TOPIC_TRANSACTIONS_ENRICHED, TOPIC_TRANSACTIONS_NORMALIZED, TOPIC_TRANSACTIONS_RAW, TOPIC_TRANSACTIONS_VALIDATED


def test_realtime_stages_have_independent_topics_and_groups():
    assert STAGES["validation"].input_topic == TOPIC_TRANSACTIONS_RAW
    assert STAGES["normalization"].input_topic == TOPIC_TRANSACTIONS_VALIDATED
    assert STAGES["enrichment"].input_topic == TOPIC_TRANSACTIONS_NORMALIZED
    assert STAGES["processing"].input_topic == TOPIC_TRANSACTIONS_ENRICHED
    assert len({stage.consumer_group for stage in STAGES.values()}) == 4