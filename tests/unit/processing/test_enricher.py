from datetime import UTC, datetime
from uuid import uuid4

import pytest

from src.ingestion.schemas import HostMetadata, JoinedEvent, RawEvent, VulnerabilityMatch
from src.observability.metrics import MetricsService
from src.processing.enricher import EventEnricher


class FakeEventsRepository:
    async def get_host_metadata(self, host_id):
        return HostMetadata(
            id=host_id,
            hostname='host-1',
            cloud_provider='aws',
            region='eu-west-1',
            registered_at=datetime.now(tz=UTC),
        )


class FakeVulnerabilityRepository:
    async def list_for_library_name(self, library_name: str):
        return [
            VulnerabilityMatch(
                cve_id='CVE-2026-0001',
                severity=9,
                epss_score=0.91,
                actively_exploited=True,
                published_at=datetime.now(tz=UTC),
            )
        ]


@pytest.mark.asyncio
async def test_enricher_attaches_host_and_vulnerabilities() -> None:
    host_id = uuid4()
    kernel = RawEvent(
        event_id='evt-1',
        host_id=host_id,
        source_type='ebpf',
        event_type='kernel_trace',
        process_id='22',
        captured_at=datetime.now(tz=UTC),
        received_at=datetime.now(tz=UTC),
        library_name='openssl',
        severity=3,
        raw_payload={'a': 1},
    )
    user = RawEvent(
        event_id='evt-1',
        host_id=host_id,
        source_type='sdk_agent',
        event_type='user_trace',
        process_id='22',
        captured_at=datetime.now(tz=UTC),
        received_at=datetime.now(tz=UTC),
        library_name='openssl',
        function_name='SSL_read',
        severity=4,
        raw_payload={'b': 2},
    )
    joined = JoinedEvent(event_id='evt-1', host_id=host_id, process_id='22', kernel=kernel, user=user)
    enricher = EventEnricher(FakeEventsRepository(), FakeVulnerabilityRepository(), MetricsService())

    enriched = await enricher.enrich(joined)

    assert enriched.host is not None
    assert enriched.vulnerabilities[0].actively_exploited is True
    assert enriched.severity >= 9
