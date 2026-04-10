"""Idempotency checks backed by Redis and PostgreSQL."""

import structlog
from redis.asyncio import Redis
from redis.exceptions import ResponseError

from src.config import Settings
from src.processing.init import IdempotencyError
from src.storage.repositories.events import EventsRepository


class IdempotencyService:
    """Provides fast-path and fallback duplicate detection."""

    def __init__(
        self,
        redis_client: Redis,
        events_repository: EventsRepository,
        settings: Settings,
    ) -> None:
        """Store dependencies for duplicate detection.

        Args:
            redis_client: Redis client.
            events_repository: Events repository.
            settings: Application settings.

        Returns:
            None.
        """
        self._redis = redis_client
        self._events_repository = events_repository
        self._settings = settings
        self._logger = structlog.get_logger(__name__)

    async def check(self, event_id: str, consumer_group: str) -> bool:
        """Check whether an event was already processed.

        Args:
            event_id: Upstream event identifier.
            consumer_group: Consumer group identifier.

        Returns:
            True when the event is a duplicate.
        """
        key = f'{self._settings.REDIS_BLOOM_KEY}:{consumer_group}'
        try:
            bloom_hit = await self._redis.execute_command('BF.EXISTS', key, event_id)
            if int(bloom_hit) == 0:
                return False
        except ResponseError:
            cached = await self._redis.sismember(key, event_id)
            if not cached:
                return False
        except Exception as exc:
            self._logger.error('idempotency.redis_check_failed', event_id=event_id, error=str(exc))
            raise IdempotencyError(str(exc)) from exc
        return await self._events_repository.has_processed_event(event_id, consumer_group)

    async def mark(self, event_id: str, consumer_group: str) -> None:
        """Persist idempotency state to PostgreSQL and Redis.

        Args:
            event_id: Upstream event identifier.
            consumer_group: Consumer group identifier.

        Returns:
            None.
        """
        key = f'{self._settings.REDIS_BLOOM_KEY}:{consumer_group}'
        await self._events_repository.mark_processed_event(event_id, consumer_group)
        try:
            await self._redis.execute_command('BF.ADD', key, event_id)
        except ResponseError:
            await self._redis.sadd(key, event_id)
        except Exception as exc:
            self._logger.error('idempotency.redis_mark_failed', event_id=event_id, error=str(exc))
            raise IdempotencyError(str(exc)) from exc
