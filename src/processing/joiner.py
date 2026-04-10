"""Redis-backed joiner for kernel and user runtime events."""

import asyncio

from redis.asyncio import Redis

from src.config import Settings
from src.ingestion.schemas import JoinedEvent, RawEvent
from src.processing.pending import PendingEnrichmentService


class EventJoiner:
    """Correlates short-lived kernel and user events by host and process."""

    def __init__(
        self,
        redis_client: Redis,
        pending_service: PendingEnrichmentService,
        settings: Settings,
    ) -> None:
        """Store joiner dependencies.

        Args:
            redis_client: Redis client.
            pending_service: Pending enrichment service.
            settings: Application settings.

        Returns:
            None.
        """
        self._redis = redis_client
        self._pending_service = pending_service
        self._settings = settings
        self._matched_keys: set[str] = set()
        self._pending_tasks: set[asyncio.Task[None]] = set()

    async def handle(self, event: RawEvent) -> JoinedEvent | None:
        """Join an event with its counterpart when available.

        Args:
            event: Raw runtime event.

        Returns:
            Joined event when both sides are present, otherwise None.
        """
        current_kind = 'kernel' if event.event_type.startswith('kernel') else 'user'
        other_kind = 'user' if current_kind == 'kernel' else 'kernel'
        other_key = self._buffer_key(event, other_kind)
        other_value = await self._redis.get(other_key)
        if other_value is not None:
            await self._redis.delete(other_key)
            self._matched_keys.update({other_key, self._buffer_key(event, current_kind)})
            other_event = RawEvent.model_validate_json(other_value)
            return self._build_joined(event, other_event)
        own_key = self._buffer_key(event, current_kind)
        await self._redis.set(own_key, event.model_dump_json(), px=self._settings.JOIN_TTL_MS)
        self._schedule_pending_write(own_key, event)
        return None

    def _schedule_pending_write(self, key: str, event: RawEvent) -> None:
        """Schedule persistence for an unmatched event.

        Args:
            key: Redis buffer key.
            event: Raw runtime event.

        Returns:
            None.
        """
        task = asyncio.create_task(self._write_pending_if_unmatched(key, event))
        self._pending_tasks.add(task)
        task.add_done_callback(self._pending_tasks.discard)

    async def _write_pending_if_unmatched(self, key: str, event: RawEvent) -> None:
        """Persist the event if no join occurs before TTL expiry.

        Args:
            key: Redis buffer key.
            event: Raw runtime event.

        Returns:
            None.
        """
        await asyncio.sleep(self._settings.PENDING_WRITE_DELAY_MS / 1000)
        if key in self._matched_keys:
            self._matched_keys.discard(key)
            return
        await self._pending_service.persist_orphan(event)

    def _build_joined(self, current: RawEvent, other: RawEvent) -> JoinedEvent:
        """Construct a joined event in kernel-user order.

        Args:
            current: Current runtime event.
            other: Previously buffered event.

        Returns:
            Joined runtime event.
        """
        kernel = current if current.event_type.startswith('kernel') else other
        user = current if current.event_type.startswith('user') else other
        return JoinedEvent(
            event_id=user.event_id if user is not None else current.event_id,
            host_id=current.host_id,
            process_id=current.process_id,
            kernel=kernel,
            user=user,
        )

    def _buffer_key(self, event: RawEvent, kind: str) -> str:
        """Build a consistent Redis key for a buffered event.

        Args:
            event: Raw runtime event.
            kind: Buffer kind, such as kernel or user.

        Returns:
            Redis key.
        """
        return f'oligo:join:{event.host_id}:{event.process_id}:{kind}'
