from collections.abc import Iterator

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.database.session import get_db

# Appears in the simulated driver error; must never reach the response body.
SECRET_ERROR_DETAIL = "password authentication failed for user provideriq"


class _UnavailableSession:
    """Stands in for a Session whose database is down."""

    def execute(self, *args: object, **kwargs: object) -> None:
        raise OperationalError("SELECT 1", {}, Exception(SECRET_ERROR_DETAIL))


def _unavailable_db() -> Iterator[_UnavailableSession]:
    yield _UnavailableSession()


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert body["app"] == "ProviderIQ"
    assert body["environment"] == "test"


def test_health_returns_503_when_database_is_unavailable(app: FastAPI) -> None:
    app.dependency_overrides[get_db] = _unavailable_db

    with TestClient(app) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["database"] == "unavailable"
    assert SECRET_ERROR_DETAIL not in response.text


def test_unknown_route_returns_404(client: TestClient) -> None:
    assert client.get("/api/v1/does-not-exist").status_code == 404
