from app.infrastructure.redis_client import redis_client
from app.infrastructure.kafka_producer import kafka_producer
from app.infrastructure.opensearch_client import opensearch_client

__all__ = ["redis_client", "kafka_producer", "opensearch_client"]
