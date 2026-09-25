from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.database.session import get_db
from app.main import create_app

BACKEND_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def settings() -> Settings:
    """App settings pointed at the test database."""
    base = Settings()
    if not base.test_database_url:
        pytest.fail("TEST_DATABASE_URL is not set; add it to the repo-root .env (see .env.example)")
    if base.test_database_url == base.database_url:
        pytest.fail("TEST_DATABASE_URL must point at a different database than DATABASE_URL")
    return Settings(environment="test", database_url=base.test_database_url)


@pytest.fixture(scope="session")
def db_engine(settings: Settings) -> Iterator[Engine]:
    """Engine for the test database, migrated to head once per test run."""
    engine = create_engine(settings.database_url)
    alembic_config = Config(str(BACKEND_DIR / "alembic.ini"))
    with engine.begin() as connection:
        # env.py uses this connection instead of DATABASE_URL.
        alembic_config.attributes["connection"] = connection
        command.upgrade(alembic_config, "head")
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine: Engine) -> Iterator[Session]:
    """A Session inside an outer transaction that is rolled back after the test.

    join_transaction_mode="create_savepoint" turns session.commit() in the code under test
    into a SAVEPOINT release, so nothing a test writes survives the rollback.
    """
    connection = db_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    return create_app(settings)


@pytest.fixture
def client(app: FastAPI, db_session: Session) -> Iterator[TestClient]:
    """Test client whose requests share the test's rolled-back db_session."""
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as test_client:
        yield test_client
