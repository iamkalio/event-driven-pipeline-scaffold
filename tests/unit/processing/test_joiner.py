from datetime import UTC, datetime
from uuid import uuid4

import pytest

from src.config import Settings
from src.ingestion.schemas import RawEvent
from src.processing.joiner import EventJoiner


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def set(self, key: str, value: str, px: int) -> None:
        self.store[key] = value

    async def delete(self, key: str) -> None:
        self.store.pop(key, None)


class FakePendingService:
    def __init__(self) -> None:
        self.events: list[str] = []

    async def persist_orphan(self, event: RawEvent) -> None:
        self.events.append(event.event_id)


@pytest.mark.asyncio
async def test_joiner_returns_joined_event_when_counterpart_exists() -> None:
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
        JOIN_TTL_MS=200,
        PENDING_WRITE_DELAY_MS=250,
    )
    redis = FakeRedis()
    pending = FakePendingService()
    joiner = EventJoiner(redis, pending, settings)
    host_id = uuid4()
    kernel = RawEvent(
        event_id='evt-1',
        host_id=host_id,
        source_type='ebpf',
        event_type='kernel_trace',
        process_id='42',
        captured_at=datetime.now(tz=UTC),
        received_at=datetime.now(tz=UTC),
        syscall_type='connect',
        raw_payload={'side': 'kernel'},
    )
    user = RawEvent(
        event_id='evt-1',
        host_id=host_id,
        source_type='sdk_agent',
        event_type='user_trace',
        process_id='42',
        captured_at=datetime.now(tz=UTC),
        received_at=datetime.now(tz=UTC),
        function_name='open_socket',
        raw_payload={'side': 'user'},
    )

    assert await joiner.handle(kernel) is None
    joined = await joiner.handle(user)

    assert joined is not None
    assert joined.kernel is not None
    assert joined.user is not None
    assert pending.events == []
