"""Runtime event pipeline bootstrap and routing logic."""

import asyncio

import structlog

from src.ai.inline_scorer import InlineScorer
from src.alerting.dedup import AlertDeduplicator
from src.alerting.jira import JiraNotifier
from src.alerting.slack import SlackNotifier
from src.config import Settings
from src.ingestion.producer import KafkaProducerWrapper
from src.ingestion.schemas import EnrichedEvent, RawEvent
from src.observability.logging import configure_logging
from src.observability.metrics import MetricsService
from src.processing.enricher import EventEnricher
from src.processing.idempotency import IdempotencyService
from src.processing.joiner import EventJoiner
from src.processing.pending import PendingEnrichmentService
from src.processing.threat_engine import ThreatEngine
from src.storage.db import close_database_resources, create_database_resources
from src.storage.repositories.alerts import AlertsRepository
from src.storage.repositories.events import EventsRepository
from src.storage.repositories.libraries import LibrariesRepository
from src.storage.repositories.vulnerabilities import VulnerabilitiesRepository
from src.streaming.consumer import BaseKafkaConsumer
from src.streaming.dlq import DLQPublisher


class RuntimePipeline:
    """Coordinates idempotency, enrichment, scoring, and alerting."""

    def __init__(
        self,
        consumer_group: str,
        events_repository: EventsRepository,
        vulnerabilities_repository: VulnerabilitiesRepository,
        libraries_repository: LibrariesRepository,
        alerts_repository: AlertsRepository,
        idempotency: IdempotencyService,
        joiner: EventJoiner,
        enricher: EventEnricher,
        scorer: InlineScorer,
        threat_engine: ThreatEngine,
        deduplicator: AlertDeduplicator,
        slack: SlackNotifier,
        jira: JiraNotifier,
        metrics: MetricsService,
    ) -> None:
        """Store pipeline collaborators.

        Args:
            consumer_group: Consumer group identifier.
            events_repository: Events repository.
            vulnerabilities_repository: Vulnerabilities repository.
            libraries_repository: Libraries repository.
            alerts_repository: Alerts repository.
            idempotency: Idempotency service.
            joiner: Event joiner.
            enricher: Event enricher.
            scorer: Inline scorer.
            threat_engine: Threat engine.
            deduplicator: Alert deduplicator.
            slack: Slack notifier.
            jira: Jira notifier.
            metrics: Metrics service.

        Returns:
            None.
        """
        self._consumer_group = consumer_group
        self._events_repository = events_repository
        self._vulnerabilities_repository = vulnerabilities_repository
        self._libraries_repository = libraries_repository
        self._alerts_repository = alerts_repository
        self._idempotency = idempotency
        self._joiner = joiner
        self._enricher = enricher
        self._scorer = scorer
        self._threat_engine = threat_engine
        self._deduplicator = deduplicator
        self._slack = slack
        self._jira = jira
        self._metrics = metrics
        self._logger = structlog.get_logger(__name__)

    async def process(self, event: RawEvent) -> None:
        """Process one runtime event through the pipeline.

        Args:
            event: Raw runtime event.

        Returns:
            None.
        """
        if await self._idempotency.check(event.event_id, self._consumer_group):
            self._metrics.mark_processed('duplicate')
            return
        runtime_event_id = await self._events_repository.insert_event(event)
        await self._idempotency.mark(event.event_id, self._consumer_group)
        await self._attach_library(runtime_event_id, event)
        joined = await self._joiner.handle(event)
        if joined is None:
            return
        enriched = await self._enricher.enrich(joined)
        anomaly_score = await self._scorer.score(enriched)
        assessment = self._threat_engine.evaluate(enriched, anomaly_score)
        if assessment.should_alert:
            await self._dispatch_alerts(runtime_event_id, enriched, assessment.channels)
        self._logger.info('pipeline.processed', event_id=event.event_id, severity=enriched.severity)

    async def _attach_library(self, event_id, event: RawEvent) -> None:
        """Link a runtime event to a library when metadata is present.

        Args:
            event_id: Runtime event UUID.
            event: Raw runtime event.

        Returns:
            None.
        """
        if not event.library_name:
            return
        library_id = await self._libraries_repository.upsert_library(event.library_name)
        await self._libraries_repository.link_event_library(event_id, library_id, 'runtime')

    async def _dispatch_alerts(self, event_id, event: EnrichedEvent, channels: list[str]) -> None:
        """Create alerts and send them asynchronously.

        Args:
            event_id: Runtime event UUID.
            event: Enriched runtime event.
            channels: Delivery channels.

        Returns:
            None.
        """
        for channel in channels:
            should_fire, dedup_hash = await self._deduplicator.should_fire(event, channel)
            if not should_fire:
                continue
            alert = await self._alerts_repository.create_alert(event_id, channel, dedup_hash)
            self._metrics.mark_alert(channel)
            if channel == 'slack':
                await self._slack.send(alert, event)
            if channel == 'jira':
                await self._jira.send(alert, event)


class RuntimeConsumer(BaseKafkaConsumer):
    """Concrete Kafka consumer for runtime security events."""

    def __init__(self, settings: Settings, pipeline: RuntimePipeline, dlq: DLQPublisher, metrics: MetricsService) -> None:
        """Initialize the runtime consumer.

        Args:
            settings: Application settings.
            pipeline: Runtime processing pipeline.
            dlq: Dead-letter publisher.
            metrics: Metrics service.

        Returns:
            None.
        """
        super().__init__(settings.KAFKA_TOPIC_RUNTIME, 'runtime-consumer', settings, dlq, metrics)
        self._pipeline = pipeline

    async def process(self, event: RawEvent) -> None:
        """Process a raw runtime event.

        Args:
            event: Raw runtime event.

        Returns:
            None.
        """
        await self._pipeline.process(event)


async def main() -> None:
    """Start the runtime consumer service.

    Args:
        None.

    Returns:
        None.
    """
    settings = Settings()
    configure_logging(settings.LOG_LEVEL)
    metrics = MetricsService()
    db = await create_database_resources(settings)
    producer = KafkaProducerWrapper(settings)
    await producer.start()
    try:
        events_repository = EventsRepository(db.write_pool)
        vulnerabilities_repository = VulnerabilitiesRepository(db.read_pool)
        libraries_repository = LibrariesRepository(db.write_pool)
        alerts_repository = AlertsRepository(db.write_pool)
        idempotency = IdempotencyService(db.redis, events_repository, settings)
        joiner = EventJoiner(db.redis, PendingEnrichmentService(events_repository), settings)
        enricher = EventEnricher(events_repository, vulnerabilities_repository, metrics)
        pipeline = RuntimePipeline(
            consumer_group='runtime-consumer',
            events_repository=events_repository,
            vulnerabilities_repository=vulnerabilities_repository,
            libraries_repository=libraries_repository,
            alerts_repository=alerts_repository,
            idempotency=idempotency,
            joiner=joiner,
            enricher=enricher,
            scorer=InlineScorer(),
            threat_engine=ThreatEngine(),
            deduplicator=AlertDeduplicator(alerts_repository, settings),
            slack=SlackNotifier(settings, alerts_repository),
            jira=JiraNotifier(settings, alerts_repository),
            metrics=metrics,
        )
        consumer = RuntimeConsumer(settings, pipeline, DLQPublisher(producer, settings), metrics)
        await consumer.start()
        try:
            await consumer.consume_forever()
        finally:
            await consumer.stop()
    finally:
        await producer.stop()
        await close_database_resources(db)


if __name__ == '__main__':
    asyncio.run(main())
