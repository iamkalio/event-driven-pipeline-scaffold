"""Dashboard read endpoints for runtime events."""

from dataclasses import asdict
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from src.api.dependencies import get_events_repository, get_settings
from src.config import Settings
from src.ingestion.schemas import EventQuery
from src.storage.repositories.events import EventRecord, EventsRepository

router = APIRouter(tags=['events'])


class EventResponse(BaseModel):
    """Serialized event payload for dashboard reads."""

    id: UUID
    event_id: str
    host_id: UUID
    source_type: str
    library_name: str | None
    function_name: str | None
    syscall_type: str | None
    network_dest: str | None
    severity: int
    captured_at: datetime
    received_at: datetime
    resolved_at: datetime | None
    raw_payload: dict[str, object]

    @classmethod
    def from_record(cls, record: EventRecord) -> 'EventResponse':
        """Convert a repository record into an API model.

        Args:
            record: Repository event record.

        Returns:
            Event response model.
        """
        return cls(**asdict(record))


class PaginatedEventsResponse(BaseModel):
    """Paginated response for runtime event queries."""

    items: list[EventResponse]
    limit: int
    offset: int
    total: int


@router.get('/events', response_model=PaginatedEventsResponse)
async def list_events(
    severity: int = Query(default=0, ge=0, le=10),
    resolved: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    from_ts: datetime | None = Query(default=None),
    to_ts: datetime | None = Query(default=None),
    repository: EventsRepository = Depends(get_events_repository),
    settings: Settings = Depends(get_settings),
) -> PaginatedEventsResponse:
    """Return paginated runtime events using index-friendly filters.

    Args:
        severity: Minimum severity threshold.
        resolved: Whether to query resolved events.
        limit: Maximum rows to return.
        offset: Pagination offset.
        from_ts: Optional lower bound for capture time.
        to_ts: Optional upper bound for capture time.
        repository: Events repository.
        settings: Application settings.

    Returns:
        Paginated runtime events response.
    """
    query = EventQuery(
        severity=severity,
        resolved=resolved,
        limit=min(limit, settings.API_MAX_LIMIT),
        offset=offset,
        from_ts=from_ts,
        to_ts=to_ts,
    )
    rows, total = await repository.list_events(query)
    return PaginatedEventsResponse(
        items=[EventResponse.from_record(row) for row in rows],
        limit=query.limit,
        offset=query.offset,
        total=total,
    )
