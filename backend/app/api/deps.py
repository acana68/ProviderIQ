from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.database.session import get_db
from app.repositories.provider_repository import ProviderRepository
from app.repositories.reference_repository import ReferenceRepository


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
