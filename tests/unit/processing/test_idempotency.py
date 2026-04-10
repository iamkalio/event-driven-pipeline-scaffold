import pytest
from redis.exceptions import ResponseError

from src.config import Settings
from src.processing.idempotency import IdempotencyService


class FakeRedis:
    def __init__(self) -> None:
        self.values: set[str] = set()

    async def execute_command(self, command: str, key: str, event_id: str):
        if command == 'BF.EXISTS':
            return int(event_id in self.values)
        if command == 'BF.ADD':
            raise ResponseError('bloom unavailable')
        raise AssertionError('unexpected command')

    async def sismember(self, key: str, event_id: str) -> bool:
        return event_id in self.values

    async def sadd(self, key: str, event_id: str) -> None:
        self.values.add(event_id)


class FakeEventsRepository:
    def __init__(self) -> None:
        self.processed: set[tuple[str, str]] = set()

    async def has_processed_event(self, event_id: str, consumer_group: str) -> bool:
        return (event_id, consumer_group) in self.processed

    async def mark_processed_event(self, event_id: str, consumer_group: str) -> None:
        self.processed.add((event_id, consumer_group))


@pytest.mark.asyncio
async def test_idempotency_uses_db_fallback_after_cache_hit() -> None:
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
        REDIS_BLOOM_KEY='oligo:test:bloom',
    )
    redis = FakeRedis()
    repo = FakeEventsRepository()
    service = IdempotencyService(redis, repo, settings)

    await service.mark('evt-1', 'cg-1')

    assert await service.check('evt-1', 'cg-1') is True
    assert await service.check('evt-2', 'cg-1') is False
