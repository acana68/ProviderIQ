from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.database.session import get_db


def get_app_settings(request: Request) -> Settings:
    """The settings this app instance was built with (see create_app)."""
    return request.app.state.settings


SettingsDep = Annotated[Settings, Depends(get_app_settings)]
DbSession = Annotated[Session, Depends(get_db)]
