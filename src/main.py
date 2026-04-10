"""FastAPI application entrypoint with lifecycle-managed dependencies."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.responses import Response

from src.api.routers.alerts import router as alerts_router
from src.api.routers.events import router as events_router
from src.api.routers.health import router as health_router
from src.api.routers.vulnerabilities import router as vulnerabilities_router
from src.config import Settings
from src.observability.logging import configure_logging
from src.observability.metrics import MetricsService
from src.storage.db import close_database_resources, create_database_resources


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and dispose application resources.

    Args:
        app: FastAPI application.

    Returns:
        Lifespan context manager.
    """
    settings = Settings()
    configure_logging(settings.LOG_LEVEL)
    app.state.settings = settings
    app.state.metrics = MetricsService()
    app.state.db = await create_database_resources(settings)
    try:
        yield
    finally:
        await close_database_resources(app.state.db)


app = FastAPI(title='oligo-backend', lifespan=lifespan)
app.include_router(health_router)
app.include_router(events_router)
app.include_router(alerts_router)
app.include_router(vulnerabilities_router)


@app.get('/metrics')
async def metrics() -> Response:
    """Expose Prometheus metrics for scraping.

    Args:
        None.

    Returns:
        Prometheus exposition response.
    """
    return Response(generate_latest(app.state.metrics.registry), media_type=CONTENT_TYPE_LATEST)
