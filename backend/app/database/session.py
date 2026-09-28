import logging
from collections.abc import Iterator

from fastapi import Request
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings

logger = logging.getLogger(__name__)


def create_db_engine(settings: Settings, url: str | None = None) -> Engine:
    """Build the engine for url (default: the app's DATABASE_URL). No connection is opened
    until the first query."""
    return create_engine(
        url or settings.database_url,
        # Transparently replace pooled connections the server has dropped (e.g. DB restart).
        pool_pre_ping=True,
        # Fail fast instead of hanging when the DB is unreachable (matters for /health).
        connect_args={"connect_timeout": 5},
    )


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    # expire_on_commit=False keeps loaded objects readable after commit, e.g. when a
    # route serializes something it just saved.
    return sessionmaker(bind=engine, expire_on_commit=False)


def get_db(request: Request) -> Iterator[Session]:
    """FastAPI dependency: one Session per request, always closed afterwards.

    The session factory comes from the app (see create_app), so each app instance uses
    the database from its own settings.
    """
    session: Session = request.app.state.session_factory()
    try:
        yield session
    finally:
        session.close()


def ping(session: Session) -> bool:
    """True if the database answers SELECT 1. Errors are logged, never returned."""
    try:
        session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        logger.warning("Database ping failed", exc_info=True)
        return False
    return True
