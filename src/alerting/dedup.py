"""Alert deduplication logic backed by the alerts repository."""

import hashlib

from src.config import Settings
from src.ingestion.schemas import EnrichedEvent
from src.storage.repositories.alerts import AlertsRepository


class AlertDeduplicator:
    """Determines whether an alert should be fired for a channel."""

    def __init__(self, alerts_repository: AlertsRepository, settings: Settings) -> None:
        """Store the alerts repository and settings.

        Args:
            alerts_repository: Alerts repository.
            settings: Application settings.

        Returns:
            None.
        """
        self._alerts_repository = alerts_repository
        self._settings = settings

    async def should_fire(self, event: EnrichedEvent, channel: str) -> tuple[bool, str]:
        """Check whether an event should emit an alert on a channel.

        Args:
            event: Enriched runtime event.
            channel: Candidate delivery channel.

        Returns:
            Tuple of fire decision and dedup hash.
        """
        dedup_hash = hashlib.sha256(
            f'{event.event_id}:{channel}:{event.severity}'.encode('utf-8')
        ).hexdigest()
        exists = await self._alerts_repository.dedup_exists(
            dedup_hash,
            self._settings.ALERT_COOLDOWN_SECONDS,
        )
        return (not exists, dedup_hash)
