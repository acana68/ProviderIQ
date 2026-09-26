from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.ai.factory import create_llm_client
from app.api.routes import ai, health, providers, ranking, reference, search
from app.core.config import Settings, get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import install_middleware
from app.core.rate_limit import SlidingWindowRateLimiter
from app.database.session import create_db_engine, create_session_factory


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    yield
    app.state.db_engine.dispose()
    if app.state.llm_client is not None:
        app.state.llm_client.close()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)
    app.state.settings = settings
    # Built per app (not at import time) so tests can point an app at the test database.
    app.state.db_engine = create_db_engine(settings)
    app.state.session_factory = create_session_factory(app.state.db_engine)
    # None means keyword parsing only (see ai/factory.py).
    app.state.llm_client = create_llm_client(settings)
    app.state.ai_rate_limiter = SlidingWindowRateLimiter(settings.ai_rate_limit_per_minute)
    register_exception_handlers(app)
    install_middleware(app, settings)
    for router in (
        health.router,
        reference.router,
        providers.router,
        search.router,
        ai.router,
        ranking.router,
    ):
        app.include_router(router, prefix=settings.api_prefix)
    return app


app = create_app()
