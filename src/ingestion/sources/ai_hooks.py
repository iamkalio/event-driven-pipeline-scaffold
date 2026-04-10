"""AI framework hook event normalization."""

from datetime import UTC, datetime
from uuid import UUID

from src.ingestion.schemas import RawEvent, SourceType


def build_ai_hook_event(payload: dict[str, object]) -> RawEvent:
    """Normalize an AI hook payload into a raw event.

    Args:
        payload: Source payload from an AI hook.

    Returns:
        Normalized raw event.
    """
    now = datetime.now(tz=UTC)
    return RawEvent(
        event_id=str(payload['event_id']),
        host_id=UUID(str(payload['host_id'])),
        source_type=SourceType.AI_HOOKS,
        event_type=str(payload.get('event_type', 'model_hook')),
        process_id=str(payload.get('process_id', 'unknown')),
        captured_at=payload.get('captured_at', now),
        received_at=now,
        function_name=payload.get('function_name'),
        severity=int(payload.get('severity', 0)),
        raw_payload=payload,
    )
