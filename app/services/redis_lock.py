"""Redis distributed lock utilities."""
import redis.asyncio as redis
from app.core.config import get_settings

settings = get_settings()

_redis_pool: redis.ConnectionPool | None = None


async def get_redis() -> redis.Redis:
    """Get or create the async Redis connection pool."""
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = redis.ConnectionPool.from_url(
            settings.REDIS_URL,
            decode_responses=False,
            max_connections=20,
        )
    return redis.Redis(connection_pool=_redis_pool)


async def close_redis() -> None:
    """Close the Redis connection pool (call on shutdown)."""
    global _redis_pool
    if _redis_pool is not None:
        await _redis_pool.disconnect()
        _redis_pool = None


class TaskLock:
    """
    Redis SETNX-based distributed lock for task claiming.

    Usage:
        lock = TaskLock(redis, task_id)
        acquired = await lock.acquire(ttl_seconds=600)
        if acquired:
            try:
                # do work
            finally:
                await lock.release()
    """

    TASK_LOCK_PREFIX = "lock:task:"
    RUNNING_KEY_PREFIX = "running:task:"

    def __init__(self, client: redis.Redis, task_id: str):
        self.client = client
        self.task_id = task_id
        self._owned = False

    @property
    def lock_key(self) -> str:
        return f"{self.TASK_LOCK_PREFIX}{self.task_id}"

    @property
    def running_key(self) -> str:
        return f"{self.RUNNING_KEY_PREFIX}{self.task_id}"

    async def acquire(self, ttl_seconds: int = 600) -> bool:
        """Try to acquire the lock. Returns True if won."""
        acquired = await self.client.set(
            self.lock_key,
            "1",
            nx=True,      # only if not exists
            ex=ttl_seconds,
        )
        self._owned = bool(acquired)
        return self._owned

    async def release(self) -> None:
        """Release the lock if we own it."""
        if self._owned:
            await self.client.delete(self.lock_key)
            self._owned = False

    async def set_running(self, ttl_seconds: int) -> None:
        """Mark task as running in Redis with a TTL."""
        await self.client.setex(self.running_key, ttl_seconds, "running")

    async def extend_running(self, ttl_seconds: int) -> None:
        """Extend the running TTL (heartbeat keeps task alive)."""
        await self.client.expire(self.running_key, ttl_seconds)

    async def is_running(self) -> bool:
        """Check if task is currently in running state."""
        return await self.client.exists(self.running_key) > 0

    async def clear_running(self) -> None:
        """Clear the running key (task completed or failed)."""
        await self.client.delete(self.running_key)

    async def ttl(self) -> int:
        """Get remaining TTL of the running key, or -2 if not set."""
        return await self.client.ttl(self.running_key)
