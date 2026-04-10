"""Threat intelligence feed event normalization."""

from datetime import UTC, datetime
from uuid import UUID

from src.ingestion.schemas import RawEvent, SourceType


def build_threat_feed_event(payload: dict[str, object]) -> RawEvent:
    """Normalize a threat feed payload into a raw event.

    Args:
        payload: Source payload from external threat intelligence.

    Returns:
        Normalized raw event.
    """
    now = datetime.now(tz=UTC)
    return RawEvent(
        event_id=str(payload['event_id']),
        host_id=UUID(str(payload['host_id'])),
        source_type=SourceType.THREAT_FEEDS,
        event_type=str(payload.get('event_type', 'threat_match')),
        process_id=str(payload.get('process_id', 'external')),
        captured_at=payload.get('captured_at', now),
        received_at=now,
        severity=int(payload.get('severity', 0)),
        raw_payload=payload,
    )
