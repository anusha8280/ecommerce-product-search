import json
from typing import Optional, Any
import redis
from app.config import settings


class RedisClientWrapper:
    def __init__(self):
        self.client: Optional[redis.Redis] = None
        self._available: Optional[bool] = None  # None=untried, False=known unavailable

    def connect(self):
        try:
            self.client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                decode_responses=True,
                socket_timeout=2.0
            )
            self.client.ping()
            self._available = True
            print(f"[Redis] Connected successfully to {settings.REDIS_HOST}:{settings.REDIS_PORT}")
        except Exception as e:
            self._available = False
            print(f"[Warning] Redis connection failed ({settings.REDIS_HOST}:{settings.REDIS_PORT}): {e}")
            self.client = None

    def get(self, key: str) -> Optional[Any]:
        if not self.client and self._available is not False:
            self.connect()
        if not self.client:
            return None
        try:
            value = self.client.get(key)
            if value:
                return json.loads(value)
        except Exception as e:
            print(f"[Warning] Redis get error for key '{key}': {e}")
        return None

    def setex(self, key: str, ttl: int, value: Any) -> bool:
        if not self.client and self._available is not False:
            self.connect()
        if not self.client:
            return False
        try:
            serialized = json.dumps(value)
            return bool(self.client.setex(key, ttl, serialized))
        except Exception as e:
            print(f"[Warning] Redis setex error for key '{key}': {e}")
            return False

    def delete(self, key: str) -> bool:
        if not self.client and self._available is not False:
            self.connect()
        if not self.client:
            return False
        try:
            return bool(self.client.delete(key))
        except Exception as e:
            print(f"[Warning] Redis delete error for key '{key}': {e}")
            return False

    def is_healthy(self) -> bool:
        if self._available is False:
            return False
        if not self.client and self._available is None:
            self.connect()
        if not self.client:
            return False
        try:
            return self.client.ping()
        except Exception:
            self._available = False
            return False


redis_client = RedisClientWrapper()
