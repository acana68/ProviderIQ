from collections.abc import Callable, Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.database.session import get_db
from tests.helpers import assert_error

MakeClient = Callable[..., TestClient]

# Appears in the simulated driver error; must never reach the response body.
SECRET_ERROR_DETAIL = "password authentication failed for user provideriq"


class _UnavailableSession:
    """Stands in for a Session whose database is down."""

    def execute(self, *args: object, **kwargs: object) -> None:
        raise OperationalError("SELECT 1", {}, Exception(SECRET_ERROR_DETAIL))


def _unavailable_db() -> Iterator[_UnavailableSession]:
    yield _UnavailableSession()


def test_liveness_returns_ok(client: TestClient) -> None:
    response = client.get("/api/v1/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_liveness_does_not_touch_the_database(app: FastAPI) -> None:
    app.dependency_overrides[get_db] = _unavailable_db

    with TestClient(app) as client:
        response = client.get("/api/v1/health/live")

    assert response.status_code == 200


def test_readiness_returns_ok(client: TestClient) -> None:
    response = client.get("/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_readiness_returns_503_when_database_is_unavailable(app: FastAPI) -> None:
    app.dependency_overrides[get_db] = _unavailable_db

    with TestClient(app) as client:
        response = client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "database": "unavailable"}
    assert SECRET_ERROR_DETAIL not in response.text


@pytest.mark.parametrize("path", ["/api/v1/health/live", "/api/v1/health/ready"])
def test_health_does_not_reveal_version_or_environment(client: TestClient, path: str) -> None:
    body = client.get(path).text

    assert "0.1.0" not in body
    assert "test" not in body
    assert "ProviderIQ" not in body


def test_old_health_path_is_gone(client: TestClient) -> None:
    assert_error(client.get("/api/v1/health"), 404, "NOT_FOUND")


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_api_docs_are_served_outside_prod(make_client: MakeClient, path: str) -> None:
    assert make_client(environment="dev").get(path).status_code == 200


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_api_docs_are_disabled_in_prod(make_client: MakeClient, path: str) -> None:
    assert_error(make_client(environment="prod").get(path), 404, "NOT_FOUND")


def test_unknown_route_returns_404(client: TestClient) -> None:
    error = assert_error(client.get("/api/v1/does-not-exist"), 404, "NOT_FOUND")

    assert error["message"] == "Not Found"
