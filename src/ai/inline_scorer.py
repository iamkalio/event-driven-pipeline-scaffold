"""Low-latency inline anomaly scoring for enriched events."""

from src.ingestion.schemas import EnrichedEvent


class InlineScorer:
    """Computes a lightweight heuristic score in the consumer loop."""

    async def score(self, event: EnrichedEvent) -> float:
        """Compute a sub-10ms heuristic score.

        Args:
            event: Enriched runtime event.

        Returns:
            Score in the range 0.0-1.0.
        """
        score = 0.1
        if event.severity >= 8:
            score += 0.45
        if event.network_dest:
            score += 0.15
        if any(match.actively_exploited for match in event.vulnerabilities):
            score += 0.25
        if event.function_name and 'exec' in event.function_name.lower():
            score += 0.15
        return min(score, 1.0)
