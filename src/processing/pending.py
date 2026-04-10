"""Pending enrichment domain service for orphaned events."""

from src.ingestion.schemas import RawEvent
from src.storage.repositories.events import EventsRepository


class PendingEnrichmentService:
    """Persists unmatched events for later correlation."""

    def __init__(self, events_repository: EventsRepository) -> None:
        """Store the events repository.

        Args:
            events_repository: Repository used for pending writes.

        Returns:
            None.
        """
        self._events_repository = events_repository

    async def persist_orphan(self, event: RawEvent) -> None:
        """Persist an unmatched event after the join TTL expires.

        Args:
            event: Orphaned raw event.

        Returns:
            None.
        """
        await self._events_repository.record_pending_enrichment(event)
