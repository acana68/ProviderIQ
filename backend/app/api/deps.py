from typing import Annotated

from fastapi import Depends, Request

from app.core.config import Settings


def get_app_settings(request: Request) -> Settings:
    """The settings this app instance was built with (see create_app)."""
    return request.app.state.settings


SettingsDep = Annotated[Settings, Depends(get_app_settings)]
