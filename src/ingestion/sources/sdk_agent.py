"""Language SDK agent event normalization."""

from datetime import UTC, datetime
from uuid import UUID

from src.ingestion.schemas import RawEvent, SourceType


def build_sdk_agent_event(payload: dict[str, object]) -> RawEvent:
    """Normalize an SDK agent payload into a raw event.

    Args:
        payload: Source payload from an SDK agent.

    Returns:
        Normalized raw event.
    """
    now = datetime.now(tz=UTC)
    return RawEvent(
        event_id=str(payload['event_id']),
        host_id=UUID(str(payload['host_id'])),
        source_type=SourceType.SDK_AGENT,
        event_type=str(payload.get('event_type', 'user_trace')),
        process_id=str(payload.get('process_id', 'unknown')),
        captured_at=payload.get('captured_at', now),
        received_at=now,
        library_name=payload.get('library_name'),
        function_name=payload.get('function_name'),
        severity=int(payload.get('severity', 0)),
        raw_payload=payload,
    )
