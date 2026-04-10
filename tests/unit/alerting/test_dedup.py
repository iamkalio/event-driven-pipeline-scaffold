from datetime import UTC, datetime
from uuid import uuid4

import pytest

from src.alerting.dedup import AlertDeduplicator
from src.config import Settings
from src.ingestion.schemas import EnrichedEvent


class FakeAlertsRepository:
    def __init__(self) -> None:
        self.hashes: set[str] = set()

    async def dedup_exists(self, dedup_hash: str, cooldown_seconds: int) -> bool:
        return dedup_hash in self.hashes


@pytest.mark.asyncio
async def test_dedup_blocks_previously_fired_alerts() -> None:
    settings = Settings.model_construct(
        KAFKA_BOOTSTRAP_SERVERS='kafka:9092',
        KAFKA_TOPIC_RUNTIME='runtime-events',
        KAFKA_TOPIC_THREAT='threat-events',
        KAFKA_TOPIC_DLQ='runtime-events-dlq',
        POSTGRES_DSN='postgres://unused',
        PGBOUNCER_DSN='postgres://unused',
        REDIS_URL='redis://unused',
        SLACK_WEBHOOK_URL='https://example.com',
        JIRA_BASE_URL='https://example.atlassian.net',
        JIRA_API_TOKEN='token',
        AI_MODEL_SERVER_URL='dns:///model-server:50051',
        ENVIRONMENT='test',
        LOG_LEVEL='INFO',
        ALERT_COOLDOWN_SECONDS=900,
    )
    repo = FakeAlertsRepository()
    dedup = AlertDeduplicator(repo, settings)
    event = EnrichedEvent(
        event_id='evt-1',
        host_id=uuid4(),
        process_id='12',
        source_type='sdk_agent',
        captured_at=datetime.now(tz=UTC),
        severity=8,
        vulnerabilities=[],
    )

    should_fire, dedup_hash = await dedup.should_fire(event, 'slack')
    repo.hashes.add(dedup_hash)
    should_fire_again, _ = await dedup.should_fire(event, 'slack')

    assert should_fire is True
    assert should_fire_again is False
