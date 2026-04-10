"""Repositories for vulnerability lookups and event-vulnerability links."""

from uuid import UUID

import asyncpg

from src.ingestion.schemas import VulnerabilityMatch


class VulnerabilitiesRepository:
    """Repository for vulnerability context."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        """Store the asyncpg pool for later use.

        Args:
            pool: Asyncpg connection pool.

        Returns:
            None.
        """
        self._pool = pool

    async def list_for_library_name(self, library_name: str | None) -> list[VulnerabilityMatch]:
        """Return vulnerabilities historically associated with a library.

        Args:
            library_name: Library name from the runtime event.

        Returns:
            Matched vulnerabilities sorted by risk.
        """
        if not library_name:
            return []
        async with self._pool.acquire() as connection:
            rows = await connection.fetch(
                '''
                SELECT DISTINCT v.cve_id, v.severity, v.epss_score,
                       v.actively_exploited, v.published_at
                FROM vulnerabilities AS v
                JOIN event_vulnerabilities AS ev ON ev.vuln_id = v.id
                JOIN event_libraries AS el ON el.event_id = ev.event_id
                JOIN libraries AS l ON l.id = el.library_id
                WHERE l.name = $1
                ORDER BY v.severity DESC, v.epss_score DESC
                LIMIT 10
                ''',
                library_name,
            )
        return [VulnerabilityMatch.model_validate(dict(row)) for row in rows]

    async def link_event_vulnerability(self, event_id: UUID, vuln_id: UUID, match_reason: str) -> None:
        """Create a link between an event and a vulnerability.

        Args:
            event_id: Runtime event UUID.
            vuln_id: Vulnerability UUID.
            match_reason: Explanation of the match.

        Returns:
            None.
        """
        async with self._pool.acquire() as connection:
            await connection.execute(
                '''
                INSERT INTO event_vulnerabilities (event_id, vuln_id, match_reason, matched_at)
                VALUES ($1, $2, $3, NOW())
                ON CONFLICT (event_id, vuln_id) DO NOTHING
                ''',
                event_id,
                vuln_id,
                match_reason,
            )
