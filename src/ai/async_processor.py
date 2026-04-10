"""Async processor for behavioural correlation outside the ingest loop."""

from src.ai.model_client import ModelServerClient
from src.ingestion.schemas import EnrichedEvent


class AsyncBehaviourProcessor:
    """Offloads slower behavioural correlation work to another consumer group."""

    def __init__(self, model_client: ModelServerClient) -> None:
        """Store the external model client.

        Args:
            model_client: gRPC-backed model client.

        Returns:
            None.
        """
        self._model_client = model_client

    async def process(self, event: EnrichedEvent) -> dict[str, object]:
        """Produce async behavioural context for an event.

        Args:
            event: Enriched runtime event.

        Returns:
            Correlation metadata stub.
        """
        healthy = await self._model_client.healthcheck()
        return {
            'event_id': event.event_id,
            'model_server_ready': healthy,
            'correlated_behaviours': [],
        }
