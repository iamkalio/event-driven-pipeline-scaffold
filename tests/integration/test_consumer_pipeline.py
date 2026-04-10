from datetime import UTC, datetime
from uuid import uuid4

import pytest

from src.ingestion.schemas import HostMetadata, RawEvent, VulnerabilityMatch
from src.observability.metrics import MetricsService
from src.streaming.router import RuntimePipeline


class FakeEventsRepository:
    def __init__(self) -> None:
        self.inserted = []
        self.processed = set()

    async def insert_event(self, event):
        event_id = uuid4()
        self.inserted.append(event.event_id)
        return event_id

    async def get_host_metadata(self, host_id):
        return HostMetadata(
            id=host_id,
            hostname='demo-host',
            cloud_provider='aws',
            region='us-east-1',
            registered_at=datetime.now(tz=UTC),
        )

    async def has_processed_event(self, event_id: str, consumer_group: str) -> bool:
        return (event_id, consumer_group) in self.processed

    async def mark_processed_event(self, event_id: str, consumer_group: str) -> None:
        self.processed.add((event_id, consumer_group))

    async def record_pending_enrichment(self, event):
        return None


class FakeVulnerabilityRepository:
    async def list_for_library_name(self, library_name: str):
        return [
            VulnerabilityMatch(
                cve_id='CVE-2026-99',
                severity=9,
                epss_score=0.95,
                actively_exploited=True,
                published_at=datetime.now(tz=UTC),
            )
        ]


class FakeLibrariesRepository:
    async def upsert_library(self, name: str, version: str = 'unknown', language: str = 'unknown', licence: str = 'unknown'):
        return uuid4()

    async def link_event_library(self, event_id, library_id, access_type: str) -> None:
        return None


class FakeAlertsRepository:
    def __init__(self) -> None:
        self.created = []
        self.hashes = set()

    async def dedup_exists(self, dedup_hash: str, cooldown_seconds: int) -> bool:
        return False

    async def create_alert(self, event_id, channel: str, dedup_hash: str):
        self.created.append((event_id, channel, dedup_hash))
        return type('Alert', (), {'id': uuid4()})()

    async def update_delivery_status(self, alert_id, status: str) -> None:
        return None


class FakeIdempotency:
    def __init__(self) -> None:
        self.seen = set()

    async def check(self, event_id: str, consumer_group: str) -> bool:
        return (event_id, consumer_group) in self.seen

    async def mark(self, event_id: str, consumer_group: str) -> None:
        self.seen.add((event_id, consumer_group))


class FakeJoiner:
    def __init__(self, joined) -> None:
        self.joined = joined

    async def handle(self, event: RawEvent):
        return self.joined


class FakeNotifier:
    def __init__(self) -> None:
        self.sent = []

    async def send(self, alert, event) -> None:
        self.sent.append(event.event_id)


class FakeDedup:
    async def should_fire(self, event, channel: str):
        return True, f'{channel}-hash'


class FakeScorer:
    async def score(self, event):
        return 0.95


class FakeThreatEngine:
    def evaluate(self, event, anomaly_score: float):
        return type('Assessment', (), {'should_alert': True, 'channels': ['slack', 'jira']})()


@pytest.mark.asyncio
async def test_runtime_pipeline_creates_alerts_for_high_risk_event() -> None:
    host_id = uuid4()
    event = RawEvent(
        event_id='evt-1',
        host_id=host_id,
        source_type='sdk_agent',
        event_type='user_trace',
        process_id='7',
        captured_at=datetime.now(tz=UTC),
        received_at=datetime.now(tz=UTC),
        library_name='openssl',
        severity=8,
        raw_payload={'test': True},
    )
    joined = type('Joined', (), {'event_id': 'evt-1', 'host_id': host_id, 'process_id': '7', 'kernel': None, 'user': event})()
    events_repo = FakeEventsRepository()
    alerts_repo = FakeAlertsRepository()
    slack = FakeNotifier()
    jira = FakeNotifier()
    from src.processing.enricher import EventEnricher
    pipeline = RuntimePipeline(
        consumer_group='runtime-consumer',
        events_repository=events_repo,
        vulnerabilities_repository=FakeVulnerabilityRepository(),
        libraries_repository=FakeLibrariesRepository(),
        alerts_repository=alerts_repo,
        idempotency=FakeIdempotency(),
        joiner=FakeJoiner(joined),
        enricher=EventEnricher(events_repo, FakeVulnerabilityRepository(), MetricsService()),
        scorer=FakeScorer(),
        threat_engine=FakeThreatEngine(),
        deduplicator=FakeDedup(),
        slack=slack,
        jira=jira,
        metrics=MetricsService(),
    )

    await pipeline.process(event)

    assert len(alerts_repo.created) == 2
    assert slack.sent == ['evt-1']
    assert jira.sent == ['evt-1']
