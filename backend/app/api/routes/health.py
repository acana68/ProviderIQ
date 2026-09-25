from fastapi import APIRouter, Response, status

from app.api.deps import DbSession, SettingsDep
from app.database.session import ping
from app.schemas.common import HealthResponse

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": HealthResponse,
            "description": "Database unavailable",
        }
    },
)
def health(settings: SettingsDep, db: DbSession, response: Response) -> HealthResponse:
    database_ok = ping(db)
    if not database_ok:
        # Callers only learn that the DB is down; the error itself stays in the server log.
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthResponse(
        status="ok" if database_ok else "degraded",
        app=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
        database="ok" if database_ok else "unavailable",
    )
