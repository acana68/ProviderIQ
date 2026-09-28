from fastapi import APIRouter, Response, status

from app.api.deps import DbSession
from app.database.session import ping
from app.schemas.common import LivenessResponse, ReadinessResponse

router = APIRouter(prefix="/health", tags=["health"])

# Public (nginx proxies all of /api/), so neither says which version or environment runs.


@router.get("/live", response_model=LivenessResponse)
def live() -> LivenessResponse:
    """The process is up and serving. Touches nothing else, so it's cheap enough for
    any probe; it's also exempt from rate limiting."""
    return LivenessResponse(status="ok")


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": ReadinessResponse,
            "description": "Database unavailable",
        }
    },
)
def ready(db: DbSession, response: Response) -> ReadinessResponse:
    """Ready for traffic: the database answers. 503 when it doesn't. Rate limited like
    the rest of the API, since each call runs a query."""
    database_ok = ping(db)
    if not database_ok:
        # Callers only learn that the DB is down; the error itself stays in the server log.
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(
        status="ok" if database_ok else "unavailable",
        database="ok" if database_ok else "unavailable",
    )
