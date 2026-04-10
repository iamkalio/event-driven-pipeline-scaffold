"""Async Jira delivery adapter with structured retries."""

import asyncio

import httpx
import structlog

from src.alerting.init import AlertDeliveryError
from src.config import Settings
from src.ingestion.schemas import EnrichedEvent
from src.storage.repositories.alerts import AlertRecord, AlertsRepository


class JiraNotifier:
    """Creates Jira issues for high-severity runtime alerts."""

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
        """Create a Jira ticket for an enriched event with retries.

        Args:
            alert: Persisted alert row.
            event: Enriched runtime event.

        Returns:
            None.
        """
        payload = {
            'fields': {
                'summary': f'Runtime alert {event.event_id}',
                'description': f'Severity {event.severity} alert for host {event.host_id}',
            }
        }
        headers = {'Authorization': f'Bearer {self._settings.JIRA_API_TOKEN}'}
        url = f'{self._settings.JIRA_BASE_URL}/rest/api/3/issue'
        for attempt in range(1, 4):
            try:
                async with httpx.AsyncClient(timeout=self._settings.HTTP_TIMEOUT_SECONDS) as client:
                    response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                await self._alerts_repository.update_delivery_status(alert.id, 'sent')
                return
            except Exception as exc:
                self._logger.error('alerting.jira_failed', alert_id=str(alert.id), attempt=attempt, error=str(exc))
                await asyncio.sleep(0.2 * attempt)
        await self._alerts_repository.update_delivery_status(alert.id, 'failed')
        raise AlertDeliveryError(f'Jira delivery failed for alert {alert.id}')
