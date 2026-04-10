"""Liveness and readiness endpoints."""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from src.api.dependencies import get_events_repository
from src.storage.repositories.events import EventsRepository

router = APIRouter(tags=['health'])


class HealthResponse(BaseModel):
    """Serialized health status response."""

    status: str
    postgres: bool
    redis: bool


@router.get('/health', response_model=HealthResponse)
async def healthcheck(
    request: Request,
    repository: EventsRepository = Depends(get_events_repository),
) -> HealthResponse:
    """Return application liveness and readiness status.

    Args:
        request: FastAPI request object.
        repository: Events repository.

    Returns:
        Health response.
    """
    postgres_ok = await repository.ping()
    redis_ok = bool(await request.app.state.db.redis.ping())
    status = 'ok' if postgres_ok and redis_ok else 'degraded'
    return HealthResponse(status=status, postgres=postgres_ok, redis=redis_ok)
