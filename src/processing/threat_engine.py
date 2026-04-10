"""Threat scoring and alert decision rules."""

from src.ingestion.schemas import EnrichedEvent, ThreatAssessment


class ThreatEngine:
    """Applies deterministic rules over enriched runtime events."""

    def evaluate(self, event: EnrichedEvent, anomaly_score: float) -> ThreatAssessment:
        """Evaluate whether an enriched event should trigger alerts.

        Args:
            event: Enriched runtime event.
            anomaly_score: Inline anomaly score.

        Returns:
            Threat assessment describing severity and channels.
        """
        exploited = any(match.actively_exploited for match in event.vulnerabilities)
        should_alert = event.severity >= 7 or anomaly_score >= 0.8 or exploited
        channels = ['slack', 'jira'] if should_alert and event.severity >= 8 else ['slack'] if should_alert else []
        reason = 'active_exploit_or_high_score' if should_alert else 'below_alert_threshold'
        return ThreatAssessment(
            should_alert=should_alert,
            severity=event.severity,
            score=anomaly_score,
            reason=reason,
            channels=channels,
        )
