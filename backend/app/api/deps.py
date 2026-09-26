from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.database.session import get_db
from app.repositories.provider_repository import ProviderRepository
from app.repositories.reference_repository import ReferenceRepository
from app.repositories.search_log_repository import SearchLogRepository
from app.services.search_service import SearchService


def get_app_settings(request: Request) -> Settings:
    """The settings this app instance was built with (see create_app)."""
    return request.app.state.settings


SettingsDep = Annotated[Settings, Depends(get_app_settings)]
DbSession = Annotated[Session, Depends(get_db)]


def get_provider_repository(db: DbSession) -> ProviderRepository:
    return ProviderRepository(db)


def get_reference_repository(db: DbSession) -> ReferenceRepository:
    return ReferenceRepository(db)


ProviderRepo = Annotated[ProviderRepository, Depends(get_provider_repository)]
ReferenceRepo = Annotated[ReferenceRepository, Depends(get_reference_repository)]


def get_search_service(
    provider_repo: ProviderRepo, reference_repo: ReferenceRepo, db: DbSession
) -> SearchService:
    # All three repositories share the request's one session (FastAPI caches get_db).
    return SearchService(provider_repo, reference_repo, SearchLogRepository(db))


SearchServiceDep = Annotated[SearchService, Depends(get_search_service)]
