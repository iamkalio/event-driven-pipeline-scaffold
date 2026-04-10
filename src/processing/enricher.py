"""Runtime event enrichment with host and vulnerability context."""

from time import perf_counter

from src.ingestion.schemas import EnrichedEvent, JoinedEvent
from src.observability.metrics import MetricsService
from src.storage.repositories.events import EventsRepository
from src.storage.repositories.vulnerabilities import VulnerabilitiesRepository


class EventEnricher:
    """Enriches joined events with database-backed context."""

    def __init__(
        self,
        events_repository: EventsRepository,
        vulnerabilities_repository: VulnerabilitiesRepository,
        metrics: MetricsService,
    ) -> None:
        """Store dependencies for event enrichment.

        Args:
            events_repository: Events repository.
            vulnerabilities_repository: Vulnerabilities repository.
            metrics: Metrics service.

        Returns:
            None.
        """
        self._events_repository = events_repository
        self._vulnerabilities_repository = vulnerabilities_repository
        self._metrics = metrics

    async def enrich(self, event: JoinedEvent) -> EnrichedEvent:
        """Attach vulnerability and host context to a joined event.

        Args:
            event: Joined runtime event.

        Returns:
            Enriched runtime event.
        """
        start = perf_counter()
        base_event = event.user or event.kernel
        library_name = self._pick_library_name(event)
        vulnerabilities = await self._vulnerabilities_repository.list_for_library_name(library_name)
        host = await self._events_repository.get_host_metadata(event.host_id)
        severity = self._score_severity(event, vulnerabilities)
        enriched = EnrichedEvent(
            event_id=event.event_id,
            host_id=event.host_id,
            process_id=event.process_id,
            source_type=base_event.source_type,
            captured_at=base_event.captured_at,
            library_name=library_name,
            function_name=base_event.function_name,
            syscall_type=event.kernel.syscall_type if event.kernel else None,
            network_dest=str(base_event.network_dest) if base_event.network_dest else None,
            severity=severity,
            host=host,
            vulnerabilities=vulnerabilities,
            context={
                'kernel_payload': event.kernel.raw_payload if event.kernel else None,
                'user_payload': event.user.raw_payload if event.user else None,
            },
        )
        self._metrics.enrichment_latency_seconds.observe(perf_counter() - start)
        return enriched

    def _pick_library_name(self, event: JoinedEvent) -> str | None:
        """Return the best available library name for enrichment.

        Args:
            event: Joined runtime event.

        Returns:
            Library name when present.
        """
        if event.user and event.user.library_name:
            return event.user.library_name
        if event.kernel and event.kernel.library_name:
            return event.kernel.library_name
        return None

    def _score_severity(self, event: JoinedEvent, vulnerabilities: list) -> int:
        """Compute a severity score using event and EPSS context.

        Args:
            event: Joined runtime event.
            vulnerabilities: Vulnerability matches.

        Returns:
            Severity in the range 0-10.
        """
        base = max((event.user.severity if event.user else 0), (event.kernel.severity if event.kernel else 0))
        epss_score = max((match.epss_score for match in vulnerabilities), default=0.0)
        return min(10, max(base, round(epss_score * 10)))
