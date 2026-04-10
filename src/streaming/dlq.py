"""Dead-letter queue publishing helpers."""

from datetime import UTC, datetime

from src.config import Settings
from src.ingestion.producer import KafkaProducerWrapper
from src.ingestion.schemas import DLQEvent, RawEvent


class DLQPublisher:
    """Publishes failed events to the configured DLQ topic."""

    def __init__(self, producer: KafkaProducerWrapper, settings: Settings) -> None:
        """Store dependencies for dead-letter publishing.

        Args:
            producer: Kafka producer wrapper.
            settings: Application settings.

        Returns:
            None.
        """
        self._producer = producer
        self._settings = settings

    async def publish(self, event: RawEvent, topic: str, consumer_group: str, error: str) -> None:
        """Publish a failed event to the dead-letter topic.

        Args:
            event: Failed raw event.
            topic: Source topic.
            consumer_group: Consumer group name.
            error: Terminal processing error.

        Returns:
            None.
        """
        payload = DLQEvent(
            topic=topic,
            key=event.event_id,
            consumer_group=consumer_group,
            error=error,
            failed_at=datetime.now(tz=UTC),
            event=event,
        )
        await self._producer.publish(self._settings.KAFKA_TOPIC_DLQ, event.event_id, payload)
