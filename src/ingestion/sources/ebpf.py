"""eBPF sensor event normalization."""

from datetime import UTC, datetime
from uuid import UUID

from src.ingestion.schemas import RawEvent, SourceType


def build_ebpf_event(payload: dict[str, object]) -> RawEvent:
    """Normalize an eBPF payload into a raw event.

    Args:
        payload: Source payload from the eBPF sensor.

    Returns:
        Normalized raw event.
    """
    now = datetime.now(tz=UTC)
    return RawEvent(
        event_id=str(payload['event_id']),
        host_id=UUID(str(payload['host_id'])),
        source_type=SourceType.EBPF,
        event_type=str(payload.get('event_type', 'kernel_trace')),
        process_id=str(payload.get('process_id', 'unknown')),
        captured_at=payload.get('captured_at', now),
        received_at=now,
        library_name=payload.get('library_name'),
        function_name=payload.get('function_name'),
        syscall_type=payload.get('syscall_type'),
        network_dest=payload.get('network_dest'),
        severity=int(payload.get('severity', 0)),
        raw_payload=payload,
    )
