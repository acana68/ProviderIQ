from fastapi import APIRouter

from app.api.deps import SearchServiceDep
from app.schemas.common import error_responses
from app.schemas.search import SearchRequest, SearchResponse

router = APIRouter(tags=["search"])


@router.post("/search", response_model=SearchResponse, responses=error_responses(422))
def search(criteria: SearchRequest, service: SearchServiceDep) -> SearchResponse:
    """Ranked search with structured criteria.

    422 codes: VALIDATION_ERROR (malformed body), INVALID_SEARCH (unknown specialty or
    condition slug), LOCATION_NOT_FOUND (city not in GET /cities).
    """
    return service.search(criteria)
