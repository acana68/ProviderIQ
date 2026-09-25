from fastapi import FastAPI

from app.api.routes import health
from app.core.config import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title=settings.app_name, version=settings.app_version)
    app.state.settings = settings
    app.include_router(health.router, prefix=settings.api_prefix)
    return app


app = create_app()
