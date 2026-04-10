"""Dashboard read endpoints for vulnerability context."""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from src.api.dependencies import get_vulnerabilities_repository
from src.storage.repositories.vulnerabilities import VulnerabilitiesRepository

router = APIRouter(tags=['vulnerabilities'])


class VulnerabilityResponse(BaseModel):
    """Serialized vulnerability payload for dashboard reads."""

    cve_id: str
    severity: int
    epss_score: float
    actively_exploited: bool


@router.get('/vulnerabilities', response_model=list[VulnerabilityResponse])
async def list_vulnerabilities(
    library_name: str = Query(..., min_length=1),
    repository: VulnerabilitiesRepository = Depends(get_vulnerabilities_repository),
) -> list[VulnerabilityResponse]:
    """Return vulnerabilities associated with a library.

    Args:
        library_name: Library name to search.
        repository: Vulnerabilities repository.

    Returns:
        Vulnerabilities associated with the library.
    """
    matches = await repository.list_for_library_name(library_name)
    return [VulnerabilityResponse.model_validate(match.model_dump()) for match in matches]
