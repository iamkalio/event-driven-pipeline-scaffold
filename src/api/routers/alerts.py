"""Dashboard read endpoints for alerts."""

from dataclasses import asdict
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from src.api.dependencies import get_alerts_repository
from src.storage.repositories.alerts import AlertRecord, AlertsRepository

router = APIRouter(tags=['alerts'])


class AlertResponse(BaseModel):
    """Serialized alert payload for dashboard reads."""

    id: UUID
    event_id: UUID
    channel: str
    status: str
    dedup_hash: str
    fired_at: datetime
    resolved_at: datetime | None

    @classmethod
    def from_record(cls, record: AlertRecord) -> 'AlertResponse':
        """Convert a repository record into an API model.

        Args:
            record: Repository alert record.

        Returns:
            Alert response model.
        """
        return cls(**asdict(record))


class PaginatedAlertsResponse(BaseModel):
    """Paginated response for alert queries."""

    items: list[AlertResponse]
    limit: int
    offset: int
    total: int


@router.get('/alerts', response_model=PaginatedAlertsResponse)
async def list_alerts(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    repository: AlertsRepository = Depends(get_alerts_repository),
) -> PaginatedAlertsResponse:
    """Return paginated alerts for dashboard views.

    Args:
        limit: Maximum rows to return.
        offset: Pagination offset.
        repository: Alerts repository.

    Returns:
        Paginated alerts response.
    """
    rows, total = await repository.list_alerts(limit=limit, offset=offset)
    return PaginatedAlertsResponse(
        items=[AlertResponse.from_record(row) for row in rows],
        limit=limit,
        offset=offset,
        total=total,
    )
