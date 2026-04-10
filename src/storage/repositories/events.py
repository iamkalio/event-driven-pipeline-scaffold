"""Repositories for runtime events, host metadata, and idempotency state."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

import asyncpg

from src.ingestion.schemas import EnrichedEvent, EventQuery, HostMetadata, RawEvent


@dataclass(slots=True)
class EventRecord:
    """API-facing runtime event record."""

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


class EventsRepository:
    """Read and write repository for runtime events and related metadata."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        """Store the asyncpg pool for later use.

        Args:
            pool: Asyncpg connection pool.

        Returns:
            None.
        """
        self._pool = pool

    async def ping(self) -> bool:
        """Check whether PostgreSQL is reachable.

        Args:
            None.

        Returns:
            True when the database responds.
        """
        async with self._pool.acquire() as connection:
            return await connection.fetchval('SELECT TRUE')

    async def insert_event(self, event: RawEvent | EnrichedEvent) -> UUID:
        """Persist a runtime event and its identity registry record.

        Args:
            event: Raw or enriched event payload.

        Returns:
            Persisted runtime event UUID.
        """
        candidate_id = uuid4()
        async with self._pool.acquire() as connection:
            async with connection.transaction():
                await connection.execute(
                    '''
                    INSERT INTO runtime_event_registry (id, event_id, captured_at)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (event_id) DO NOTHING
                    ''',
                    candidate_id,
                    event.event_id,
                    event.captured_at,
                )
                event_id = await connection.fetchval(
                    'SELECT id FROM runtime_event_registry WHERE event_id = $1',
                    event.event_id,
                )
                await connection.execute(
                    '''
                    INSERT INTO runtime_events (
                        id, event_id, host_id, source_type, library_name,
                        function_name, syscall_type, network_dest, severity,
                        raw_payload, captured_at, received_at, resolved_at
                    ) VALUES (
                        $1, $2, $3, $4, $5,
                        $6, $7, $8, $9,
                        $10::jsonb, $11, $12, NULL
                    ) ON CONFLICT DO NOTHING
                    ''',
                    event_id,
                    event.event_id,
                    event.host_id,
                    event.source_type,
                    getattr(event, 'library_name', None),
                    getattr(event, 'function_name', None),
                    getattr(event, 'syscall_type', None),
                    getattr(event, 'network_dest', None),
                    event.severity,
                    event.model_dump_json(),
                    event.captured_at,
                    getattr(event, 'received_at', event.captured_at),
                )
        return event_id

    async def list_events(self, query: EventQuery) -> tuple[list[EventRecord], int]:
        """Fetch paginated events for dashboard views.

        Args:
            query: Event query filters.

        Returns:
            Tuple of event records and total count.
        """
        resolved_sql = 'IS NOT NULL' if query.resolved else 'IS NULL'
        params = [query.severity]
        predicates = ['severity >= $1', f'resolved_at {resolved_sql}']
        if query.from_ts is not None:
            params.append(query.from_ts)
            predicates.append(f'captured_at >= ${len(params)}')
        if query.to_ts is not None:
            params.append(query.to_ts)
            predicates.append(f'captured_at <= ${len(params)}')
        params.extend([query.limit, query.offset])
        where_clause = ' AND '.join(predicates)
        count_sql = f'SELECT COUNT(*) FROM runtime_events WHERE {where_clause}'
        list_sql = f'''
            SELECT id, event_id, host_id, source_type, library_name, function_name,
                   syscall_type, network_dest::text AS network_dest, severity,
                   captured_at, received_at, resolved_at, raw_payload
            FROM runtime_events
            WHERE {where_clause}
            ORDER BY captured_at DESC
            LIMIT ${len(params) - 1} OFFSET ${len(params)}
        '''
        async with self._pool.acquire() as connection:
            rows = await connection.fetch(list_sql, *params)
            total = await connection.fetchval(count_sql, *params[:-2])
        return [self._to_record(row) for row in rows], int(total)

    async def get_host_metadata(self, host_id: UUID) -> HostMetadata | None:
        """Return host metadata for enrichment.

        Args:
            host_id: Host identifier.

        Returns:
            Host metadata or None.
        """
        async with self._pool.acquire() as connection:
            row = await connection.fetchrow(
                'SELECT id, hostname, cloud_provider, region, registered_at FROM hosts WHERE id = $1',
                host_id,
            )
        return None if row is None else HostMetadata.model_validate(dict(row))

    async def has_processed_event(self, event_id: str, consumer_group: str) -> bool:
        """Check the processed event table for an idempotency marker.

        Args:
            event_id: Upstream event identifier.
            consumer_group: Kafka consumer group.

        Returns:
            True when the event was already processed.
        """
        async with self._pool.acquire() as connection:
            row = await connection.fetchval(
                'SELECT 1 FROM processed_events WHERE event_id = $1 AND consumer_group = $2',
                event_id,
                consumer_group,
            )
        return bool(row)

    async def mark_processed_event(self, event_id: str, consumer_group: str) -> None:
        """Record a processed event marker.

        Args:
            event_id: Upstream event identifier.
            consumer_group: Kafka consumer group.

        Returns:
            None.
        """
        async with self._pool.acquire() as connection:
            await connection.execute(
                '''
                INSERT INTO processed_events (event_id, processed_at, consumer_group)
                VALUES ($1, NOW(), $2)
                ON CONFLICT (event_id) DO UPDATE
                SET processed_at = EXCLUDED.processed_at,
                    consumer_group = EXCLUDED.consumer_group
                ''',
                event_id,
                consumer_group,
            )

    async def record_pending_enrichment(self, event: RawEvent) -> None:
        """Persist an unmatched event for later enrichment.

        Args:
            event: Orphaned raw event.

        Returns:
            None.
        """
        async with self._pool.acquire() as connection:
            await connection.execute(
                '''
                INSERT INTO pending_enrichment (
                    id, event_id, host_id, process_id, event_type, payload, arrived_at, attempt_count
                ) VALUES ($1, $2, $3, $4, $5, $6::jsonb, NOW(), 0)
                ''',
                uuid4(),
                event.event_id,
                event.host_id,
                event.process_id,
                event.event_type,
                event.model_dump_json(),
            )

    def _to_record(self, row: asyncpg.Record) -> EventRecord:
        """Map a database row to an event record.

        Args:
            row: Asyncpg result row.

        Returns:
            API-facing event record.
        """
        return EventRecord(
            id=row['id'],
            event_id=row['event_id'],
            host_id=row['host_id'],
            source_type=row['source_type'],
            library_name=row['library_name'],
            function_name=row['function_name'],
            syscall_type=row['syscall_type'],
            network_dest=row['network_dest'],
            severity=row['severity'],
            captured_at=row['captured_at'],
            received_at=row['received_at'],
            resolved_at=row['resolved_at'],
            raw_payload=dict(row['raw_payload']),
        )
