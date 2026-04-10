"""Async Slack webhook delivery with structured retries."""

import asyncio

import httpx
import structlog

from src.alerting.init import AlertDeliveryError
from src.config import Settings
from src.ingestion.schemas import EnrichedEvent
from src.storage.repositories.alerts import AlertRecord, AlertsRepository


class SlackNotifier:
    """Delivers alerts to Slack using an incoming webhook."""

    def __init__(self, settings: Settings, alerts_repository: AlertsRepository) -> None:
        """Store delivery settings and the alerts repository.

        Args:
            settings: Application settings.
            alerts_repository: Alerts repository.

        Returns:
            None.
        """
        self._settings = settings
        self._alerts_repository = alerts_repository
        self._logger = structlog.get_logger(__name__)

    async def send(self, alert: AlertRecord, event: EnrichedEvent) -> None:
        """Send an alert to Slack with retries.

        Args:
            alert: Persisted alert row.
            event: Enriched runtime event.

        Returns:
            None.
        """
        payload = {'text': f'[{event.severity}] Runtime alert for {event.event_id}'}
        for attempt in range(1, 4):
            try:
                async with httpx.AsyncClient(timeout=self._settings.HTTP_TIMEOUT_SECONDS) as client:
                    response = await client.post(self._settings.SLACK_WEBHOOK_URL, json=payload)
                response.raise_for_status()
                await self._alerts_repository.update_delivery_status(alert.id, 'sent')
                return
            except Exception as exc:
                self._logger.error('alerting.slack_failed', alert_id=str(alert.id), attempt=attempt, error=str(exc))
                await asyncio.sleep(0.2 * attempt)
        await self._alerts_repository.update_delivery_status(alert.id, 'failed')
        raise AlertDeliveryError(f'Slack delivery failed for alert {alert.id}')
