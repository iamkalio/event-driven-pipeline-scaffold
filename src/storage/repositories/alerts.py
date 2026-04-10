"""Repositories for alert deduplication and dashboard reads."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

import asyncpg


@dataclass(slots=True)
class AlertRecord:
    """Alert representation returned to the API layer."""

    id: UUID
    event_id: UUID
    channel: str
    status: str
    dedup_hash: str
    fired_at: datetime
    resolved_at: datetime | None


class AlertsRepository:
    """Repository for alert lifecycle state."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        """Store the asyncpg pool for later use.

        Args:
            pool: Asyncpg connection pool.

        Returns:
            None.
        """
        self._pool = pool

    async def dedup_exists(self, dedup_hash: str, cooldown_seconds: int) -> bool:
        """Check whether a matching alert exists within the cooldown window.

        Args:
            dedup_hash: Deduplication hash.
            cooldown_seconds: Dedup cooldown window.

        Returns:
            True when the alert should be suppressed.
        """
        async with self._pool.acquire() as connection:
            row = await connection.fetchval(
                '''
                SELECT 1
                FROM alerts
                WHERE dedup_hash = $1
                  AND fired_at >= NOW() - ($2::text || ' seconds')::interval
                ''',
                dedup_hash,
                cooldown_seconds,
            )
        return bool(row)

    async def create_alert(self, event_id: UUID, channel: str, dedup_hash: str) -> AlertRecord:
        """Create a pending alert row.

        Args:
            event_id: Runtime event UUID.
            channel: Delivery channel.
            dedup_hash: Deduplication hash.

        Returns:
            Created alert record.
        """
        alert_id = uuid4()
        async with self._pool.acquire() as connection:
            row = await connection.fetchrow(
                '''
                INSERT INTO alerts (id, event_id, channel, status, dedup_hash, fired_at, resolved_at)
                VALUES ($1, $2, $3, 'pending', $4, NOW(), NULL)
                RETURNING id, event_id, channel, status, dedup_hash, fired_at, resolved_at
                ''',
                alert_id,
                event_id,
                channel,
                dedup_hash,
            )
        return self._to_record(row)

    async def update_delivery_status(self, alert_id: UUID, status: str) -> None:
        """Update delivery status for an alert.

        Args:
            alert_id: Alert UUID.
            status: New status value.

        Returns:
            None.
        """
        async with self._pool.acquire() as connection:
            await connection.execute('UPDATE alerts SET status = $2 WHERE id = $1', alert_id, status)

    async def list_alerts(self, limit: int, offset: int) -> tuple[list[AlertRecord], int]:
        """Return paginated alerts for dashboard reads.

        Args:
            limit: Maximum rows to return.
            offset: Pagination offset.

        Returns:
            Tuple of alert records and total count.
        """
        async with self._pool.acquire() as connection:
            rows = await connection.fetch(
                '''
                SELECT id, event_id, channel, status, dedup_hash, fired_at, resolved_at
                FROM alerts
                ORDER BY fired_at DESC
                LIMIT $1 OFFSET $2
                ''',
                limit,
                offset,
            )
            total = await connection.fetchval('SELECT COUNT(*) FROM alerts')
        return [self._to_record(row) for row in rows], int(total)

    def _to_record(self, row: asyncpg.Record) -> AlertRecord:
        """Map a row into an alert record.

        Args:
            row: Asyncpg record.

        Returns:
            Alert record.
        """
        return AlertRecord(
            id=row['id'],
            event_id=row['event_id'],
            channel=row['channel'],
            status=row['status'],
            dedup_hash=row['dedup_hash'],
            fired_at=row['fired_at'],
            resolved_at=row['resolved_at'],
        )
