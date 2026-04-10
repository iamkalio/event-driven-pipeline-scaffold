"""Kafka producer wrapper for normalized runtime security events."""

import asyncio

import structlog
from aiokafka import AIOKafkaProducer
from pydantic import BaseModel

from src.config import Settings
from src.ingestion.init import PublishError


class KafkaProducerWrapper:
    """Async Kafka producer with idempotence and retry handling."""

    def __init__(self, settings: Settings) -> None:
        """Store settings for later producer initialization.

        Args:
            settings: Application settings.

        Returns:
            None.
        """
        self._settings = settings
        self._producer: AIOKafkaProducer | None = None
        self._logger = structlog.get_logger(__name__)

    async def start(self) -> None:
        """Start the underlying Kafka producer.

        Args:
            None.

        Returns:
            None.
        """
        if self._producer is not None:
            return
        self._producer = AIOKafkaProducer(
            bootstrap_servers=self._settings.KAFKA_BOOTSTRAP_SERVERS,
            acks='all',
            enable_idempotence=True,
        )
        await self._producer.start()

    async def stop(self) -> None:
        """Stop the underlying Kafka producer.

        Args:
            None.

        Returns:
            None.
        """
        if self._producer is None:
            return
        await self._producer.stop()
        self._producer = None

    async def publish(self, topic: str, key: str, payload: BaseModel) -> None:
        """Publish a Pydantic payload to Kafka as JSON.

        Args:
            topic: Destination Kafka topic.
            key: Logical record key.
            payload: Pydantic event model.

        Returns:
            None.
        """
        if self._producer is None:
            raise PublishError('Kafka producer has not been started.')
        partition_key = str(getattr(payload, 'host_id', key)).encode('utf-8')
        value = payload.model_dump_json().encode('utf-8')
        last_error: Exception | None = None
        for attempt in range(1, self._settings.KAFKA_PRODUCER_RETRIES + 1):
            try:
                await self._producer.send_and_wait(topic, value=value, key=partition_key)
                self._logger.info('kafka.publish', topic=topic, key=key, host_key=partition_key.decode('utf-8'))
                return
            except Exception as exc:
                last_error = exc
                self._logger.error('kafka.publish_failed', topic=topic, key=key, attempt=attempt, error=str(exc))
                await asyncio.sleep(0.1 * attempt)
        raise PublishError(str(last_error)) from last_error
