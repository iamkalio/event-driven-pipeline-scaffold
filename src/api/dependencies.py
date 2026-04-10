"""FastAPI dependency wiring for repositories and shared services."""

from fastapi import Request

from src.config import Settings
from src.observability.metrics import MetricsService
from src.storage.repositories.alerts import AlertsRepository
from src.storage.repositories.events import EventsRepository
from src.storage.repositories.vulnerabilities import VulnerabilitiesRepository


async def get_settings(request: Request) -> Settings:
    """Return application settings from request state.

    Args:
        request: FastAPI request object.

    Returns:
        Application settings.
    """
    return request.app.state.settings


async def get_metrics(request: Request) -> MetricsService:
    """Return the metrics service from request state.

    Args:
        request: FastAPI request object.

    Returns:
        Metrics service.
    """
    return request.app.state.metrics


async def get_events_repository(request: Request) -> EventsRepository:
    """Return a read-oriented events repository.

    Args:
        request: FastAPI request object.

    Returns:
        Events repository.
    """
    return EventsRepository(request.app.state.db.read_pool)


async def get_alerts_repository(request: Request) -> AlertsRepository:
    """Return a read-oriented alerts repository.

    Args:
        request: FastAPI request object.

    Returns:
        Alerts repository.
    """
    return AlertsRepository(request.app.state.db.read_pool)


async def get_vulnerabilities_repository(request: Request) -> VulnerabilitiesRepository:
    """Return a read-oriented vulnerabilities repository.

    Args:
        request: FastAPI request object.

    Returns:
        Vulnerabilities repository.
    """
    return VulnerabilitiesRepository(request.app.state.db.read_pool)
