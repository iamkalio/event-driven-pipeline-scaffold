"""Base Kafka consumer with manual commits, retries, and DLQ handling."""

import abc
import asyncio

import structlog
from aiokafka import AIOKafkaConsumer
from aiokafka.structs import ConsumerRecord

from src.config import Settings
from src.ingestion.schemas import RawEvent
from src.observability.metrics import MetricsService
from src.streaming.dlq import DLQPublisher


class BaseKafkaConsumer(abc.ABC):
    """Manual-commit Kafka consumer with retry and DLQ behavior."""

    def __init__(
        self,
        topic: str,
        group_id: str,
        settings: Settings,
        dlq_publisher: DLQPublisher,
        metrics: MetricsService,
    ) -> None:
        """Store consumer dependencies.

        Args:
            topic: Kafka topic name.
            group_id: Consumer group name.
            settings: Application settings.
            dlq_publisher: Dead-letter publisher.
            metrics: Metrics service.

        Returns:
            None.
        """
        self._topic = topic
        self._group_id = group_id
        self._settings = settings
        self._dlq_publisher = dlq_publisher
        self._metrics = metrics
        self._logger = structlog.get_logger(__name__)
        self._consumer: AIOKafkaConsumer | None = None

    @abc.abstractmethod
    async def process(self, event: RawEvent) -> None:
        """Process a deserialized Kafka event.

        Args:
            event: Raw runtime event.

        Returns:
            None.
        """

    async def start(self) -> None:
        """Start the underlying Kafka consumer.

        Args:
            None.

        Returns:
            None.
        """
        self._consumer = AIOKafkaConsumer(
            self._topic,
            bootstrap_servers=self._settings.KAFKA_BOOTSTRAP_SERVERS,
            group_id=self._group_id,
            enable_auto_commit=False,
            auto_offset_reset=self._settings.KAFKA_AUTO_OFFSET_RESET,
        )
        await self._consumer.start()

    async def stop(self) -> None:
        """Stop the underlying Kafka consumer.

        Args:
            None.

        Returns:
            None.
        """
        if self._consumer is not None:
            await self._consumer.stop()
            self._consumer = None

    async def consume_forever(self) -> None:
        """Consume and process Kafka events indefinitely.

        Args:
            None.

        Returns:
            None.
        """
        if self._consumer is None:
            raise RuntimeError('Consumer has not been started.')
        async for message in self._consumer:
            await self._handle_message(message)

    async def _handle_message(self, message: ConsumerRecord) -> None:
        """Process a single Kafka message with retries.

        Args:
            message: Kafka consumer record.

        Returns:
            None.
        """
        event = RawEvent.model_validate_json(message.value.decode('utf-8'))
        self._metrics.mark_ingested(event.source_type)
        for attempt in range(1, self._settings.CONSUMER_MAX_RETRIES + 1):
            try:
                await self.process(event)
                await self._consumer.commit()
                self._metrics.mark_processed('success')
                return
            except Exception as exc:
                self._logger.error('consumer.retry', attempt_number=attempt, error=str(exc), event_id=event.event_id)
                if attempt == self._settings.CONSUMER_MAX_RETRIES:
                    await self._dlq_publisher.publish(event, self._topic, self._group_id, str(exc))
                    self._metrics.mark_processed('dlq')
                    await self._consumer.commit()
                    return
                self._metrics.mark_processed('retry')
                await asyncio.sleep(0.2 * (2 ** (attempt - 1)))
