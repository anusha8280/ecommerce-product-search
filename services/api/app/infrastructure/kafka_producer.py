import json
import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from kafka import KafkaProducer
from app.config import settings


class KafkaProducerWrapper:
    def __init__(self):
        self.producer: Optional[KafkaProducer] = None
        self._available: Optional[bool] = None  # None = untried, False = known unavailable

    def connect(self):
        try:
            self.producer = KafkaProducer(
                bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                key_serializer=lambda k: str(k).encode("utf-8") if k is not None else None,
                request_timeout_ms=1000,
                max_block_ms=1000
            )
            self._available = True
            print(f"[Kafka] Producer connected to {settings.KAFKA_BOOTSTRAP_SERVERS}")
        except Exception as e:
            self._available = False
            print(f"[Warning] Kafka connection failed ({settings.KAFKA_BOOTSTRAP_SERVERS}): {e}")
            self.producer = None

    def publish_product_event(self, event_type: str, product_id: int, extra_data: Optional[Dict[str, Any]] = None) -> bool:
        if not self.producer and self._available is not False:
            self.connect()
        if not self.producer:
            print(f"[Warning] Kafka producer uninitialized. Event '{event_type}' for product {product_id} skipped.")
            return False

        event_payload = {
            "event_id": f"evt-{uuid.uuid4()}",
            "event_type": event_type,
            "product_id": product_id,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        if extra_data:
            event_payload.update(extra_data)

        try:
            future = self.producer.send(
                settings.KAFKA_TOPIC_PRODUCT_EVENTS,
                key=str(product_id),
                value=event_payload
            )
            # Flush asynchronously in background
            return True
        except Exception as e:
            print(f"[Warning] Failed to send Kafka event '{event_type}' for product {product_id}: {e}")
            return False

    def is_healthy(self) -> bool:
        # Return False immediately if already known unavailable (no blocking retry)
        if self._available is False:
            return False
        if not self.producer and self._available is None:
            self.connect()
        return self.producer is not None


kafka_producer = KafkaProducerWrapper()
