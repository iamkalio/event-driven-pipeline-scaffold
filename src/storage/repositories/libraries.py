"""Repositories for library metadata and event-library joins."""

from uuid import UUID, uuid4

import asyncpg


class LibrariesRepository:
    """Repository for software library metadata."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        """Store the asyncpg pool for later use.

        Args:
            pool: Asyncpg connection pool.

        Returns:
            None.
        """
        self._pool = pool

    async def upsert_library(
        self,
        name: str,
        version: str = 'unknown',
        language: str = 'unknown',
        licence: str = 'unknown',
    ) -> UUID:
        """Insert or return a library row.

        Args:
            name: Library name.
            version: Library version.
            language: Library language.
            licence: License identifier.

        Returns:
            Library UUID.
        """
        async with self._pool.acquire() as connection:
            existing_id = await connection.fetchval(
                'SELECT id FROM libraries WHERE name = $1 AND version = $2',
                name,
                version,
            )
            if existing_id is not None:
                return existing_id
            library_id = uuid4()
            await connection.execute(
                'INSERT INTO libraries (id, name, version, language, licence) VALUES ($1, $2, $3, $4, $5)',
                library_id,
                name,
                version,
                language,
                licence,
            )
        return library_id

    async def link_event_library(self, event_id: UUID, library_id: UUID, access_type: str) -> None:
        """Create a link between an event and a library.

        Args:
            event_id: Runtime event UUID.
            library_id: Library UUID.
            access_type: Access classification for the relationship.

        Returns:
            None.
        """
        async with self._pool.acquire() as connection:
            await connection.execute(
                '''
                INSERT INTO event_libraries (event_id, library_id, access_type)
                VALUES ($1, $2, $3)
                ON CONFLICT (event_id, library_id) DO NOTHING
                ''',
                event_id,
                library_id,
                access_type,
            )
