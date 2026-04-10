from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.api.dependencies import get_events_repository, get_settings
from src.api.routers.events import router
from src.config import Settings
from src.storage.repositories.events import EventRecord


class FakeEventsRepository:
    async def list_events(self, query):
        row = EventRecord(
            id=uuid4(),
            event_id='evt-1',
            host_id=uuid4(),
            source_type='sdk_agent',
            library_name='openssl',
            function_name='SSL_read',
            syscall_type=None,
            network_dest='10.0.0.1',
            severity=7,
            captured_at=datetime.now(tz=UTC),
            received_at=datetime.now(tz=UTC),
            resolved_at=None,
            raw_payload={'a': 1},
        )
        return [row], 1


@pytest.mark.asyncio
async def test_events_endpoint_returns_paginated_payload() -> None:
    app = FastAPI()
    app.include_router(router)
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
    )
    app.dependency_overrides[get_events_repository] = lambda: FakeEventsRepository()
    app.dependency_overrides[get_settings] = lambda: settings

    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://testserver') as client:
        response = await client.get('/events?severity=4&resolved=false')

    assert response.status_code == 200
    payload = response.json()
    assert payload['total'] == 1
    assert payload['items'][0]['event_id'] == 'evt-1'
