"""Batch processor target for baseline and SBOM-oriented workloads."""

from src.ingestion.schemas import EnrichedEvent


class BatchBaselineProcessor:
    """Aggregates enriched events for offline analysis workloads."""

    async def run(self, events: list[EnrichedEvent]) -> dict[str, object]:
        """Build a batch summary for a scheduled job.

        Args:
            events: Enriched events to aggregate.

        Returns:
            Summary payload for downstream batch consumers.
        """
        libraries = sorted({event.library_name for event in events if event.library_name})
        return {
            'event_count': len(events),
            'libraries': libraries,
            'high_severity_count': sum(1 for event in events if event.severity >= 7),
        }
