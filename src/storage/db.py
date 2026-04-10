"""Asyncpg and Redis client lifecycle helpers."""

from dataclasses import dataclass

import asyncpg
from redis.asyncio import Redis

from src.config import Settings


@dataclass(slots=True)
class DatabaseResources:
    """Database resources stored in application state."""

    write_pool: asyncpg.Pool
    read_pool: asyncpg.Pool
    redis: Redis


async def create_database_resources(settings: Settings) -> DatabaseResources:
    """Create asyncpg pools and Redis client.

    Args:
        settings: Application settings.

    Returns:
        Initialized database resources.
    """
    write_pool = await asyncpg.create_pool(
        dsn=settings.POSTGRES_DSN,
        min_size=settings.POSTGRES_POOL_MIN_SIZE,
        max_size=settings.POSTGRES_POOL_MAX_SIZE,
        command_timeout=settings.HTTP_TIMEOUT_SECONDS,
    )
    read_pool = await asyncpg.create_pool(
        dsn=settings.PGBOUNCER_DSN,
        min_size=settings.POSTGRES_POOL_MIN_SIZE,
        max_size=settings.POSTGRES_POOL_MAX_SIZE,
        command_timeout=settings.HTTP_TIMEOUT_SECONDS,
    )
    redis_client = Redis.from_url(
        settings.REDIS_URL,
        max_connections=settings.REDIS_MAX_CONNECTIONS,
        decode_responses=True,
    )
    return DatabaseResources(
        write_pool=write_pool,
        read_pool=read_pool,
        redis=redis_client,
    )


async def close_database_resources(resources: DatabaseResources) -> None:
    """Close pools and Redis connections.

    Args:
        resources: Database resources container.

    Returns:
        None.
    """
    await resources.read_pool.close()
    await resources.write_pool.close()
    await resources.redis.aclose()
