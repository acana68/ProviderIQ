import shutil
from collections.abc import Callable, Iterator
from contextlib import ExitStack
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.database.session import get_db
from app.main import create_app
from scripts.generate_data import REFERENCE_DIR, generate, write_csvs
from scripts.seed_db import seed
from tests.helpers import SECRET_ERROR_DETAIL

BACKEND_DIR = Path(__file__).resolve().parents[1]
SEED_PROVIDERS = 60


@pytest.fixture(scope="session")
def settings() -> Settings:
    """App settings pointed at the test database."""
    base = Settings()
    if not base.test_database_url:
        pytest.fail("TEST_DATABASE_URL is not set; add it to the repo-root .env (see .env.example)")
    if base.test_database_url == base.database_url:
        pytest.fail("TEST_DATABASE_URL must point at a different database than DATABASE_URL")
    # Values that tests depend on are pinned here, so a local .env can't change them.
    return Settings(
        environment="test",
        database_url=base.test_database_url,
        cors_origins=["http://localhost:5173"],
        max_request_body_bytes=65_536,
        rate_limit_per_minute=1000,
        # Tests never call a real LLM, whatever the local .env says.
        ai_provider="none",
        anthropic_api_key=None,
        ai_rate_limit_per_minute=1000,
    )


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


@pytest.fixture(scope="session")
def seed_data_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Reference CSVs plus a small generated dataset, laid out like data/. Built once."""
    data_dir = tmp_path_factory.mktemp("seed-data")
    shutil.copytree(REFERENCE_DIR, data_dir / "reference")
    write_csvs(*generate(n_providers=SEED_PROVIDERS, seed=11), data_dir / "generated")
    return data_dir


@pytest.fixture
def seeded_db(db_session: Session, seed_data_dir: Path) -> Session:
    """db_session with the seed data loaded; rolled back after the test like any other."""
    seed(db_session, seed_data_dir)
    # Start with an empty identity map, so tests see the queries a fresh request would run.
    db_session.expunge_all()
    return db_session


def _add_test_routes(app: FastAPI) -> None:
    """Routes that exist only in tests, for exercising error handling and middleware."""

    async def boom() -> None:
        raise RuntimeError(SECRET_ERROR_DETAIL)

    async def echo_body_size(request: Request) -> dict[str, int]:
        return {"size": len(await request.body())}

    app.add_api_route("/api/v1/_test/boom", boom, methods=["GET"])
    app.add_api_route("/api/v1/_test/echo", echo_body_size, methods=["POST"])


@pytest.fixture
def make_client(settings: Settings, db_session: Session) -> Iterator[Callable[..., TestClient]]:
    """Build a client for an app with some settings overridden, plus the test-only routes.

    Example: make_client(rate_limit_per_minute=3)
    """
    with ExitStack() as stack:

        def make(**overrides: Any) -> TestClient:
            app = create_app(settings.model_copy(update=overrides))
            app.dependency_overrides[get_db] = lambda: db_session
            _add_test_routes(app)
            return stack.enter_context(TestClient(app))

        yield make
