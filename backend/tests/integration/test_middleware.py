import logging
import uuid
from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient
from httpx2 import Response

from app.core.logging import JsonFormatter
from tests.helpers import assert_error

ALLOWED_ORIGIN = "http://allowed.example"
OTHER_ORIGIN = "http://evil.example"

MakeClient = Callable[..., TestClient]


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
    except ValueError:
        return False
    return True


def _assert_common_headers(response: Response) -> None:
    assert response.headers["X-Request-ID"]
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Access-Control-Allow-Origin"] == ALLOWED_ORIGIN


# --- Request ID -----------------------------------------------------------------------


def test_request_id_is_generated_when_missing(client: TestClient) -> None:
    response = client.get("/api/v1/health/live")

    assert _is_uuid(response.headers["X-Request-ID"])
    assert response.headers["X-Content-Type-Options"] == "nosniff"


def test_valid_incoming_request_id_is_echoed(client: TestClient) -> None:
    response = client.get("/api/v1/does-not-exist", headers={"X-Request-ID": "abc-123_DEF"})

    assert response.headers["X-Request-ID"] == "abc-123_DEF"
    assert response.json()["error"]["request_id"] == "abc-123_DEF"


@pytest.mark.parametrize("incoming", ["has spaces", "semi;colon", "x" * 65, ""])
def test_invalid_incoming_request_id_is_replaced(client: TestClient, incoming: str) -> None:
    response = client.get("/api/v1/health/live", headers={"X-Request-ID": incoming})

    assert response.headers["X-Request-ID"] != incoming
    assert _is_uuid(response.headers["X-Request-ID"])


def test_access_log_has_path_without_query_string(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="app.access")

    response = client.get("/api/v1/providers", params={"city": "Private Town"})

    [record] = [r for r in caplog.records if r.name == "app.access"]
    assert record.method == "GET"
    assert record.path == "/api/v1/providers"
    assert record.status == response.status_code
    assert record.duration_ms >= 0
    assert "Private" not in JsonFormatter().format(record)


# --- Body size limit ------------------------------------------------------------------


@pytest.fixture
def small_body_client(make_client: MakeClient) -> TestClient:
    return make_client(max_request_body_bytes=100, cors_origins=[ALLOWED_ORIGIN])


def _chunks(total: int) -> Iterator[bytes]:
    """A streamed body, which is sent without a Content-Length header."""
    for _ in range(total // 10):
        yield b"x" * 10


def test_body_within_limit_is_accepted(small_body_client: TestClient) -> None:
    response = small_body_client.post("/api/v1/_test/echo", content=b"x" * 100)

    assert response.status_code == 200
    assert response.json() == {"size": 100}


def test_body_over_limit_with_content_length_returns_413(small_body_client: TestClient) -> None:
    response = small_body_client.post(
        "/api/v1/_test/echo", content=b"x" * 101, headers={"Origin": ALLOWED_ORIGIN}
    )

    assert_error(response, 413, "PAYLOAD_TOO_LARGE")
    _assert_common_headers(response)


def test_streamed_body_is_limited_without_content_length(small_body_client: TestClient) -> None:
    small = small_body_client.post("/api/v1/_test/echo", content=_chunks(50))
    large = small_body_client.post("/api/v1/_test/echo", content=_chunks(150))

    assert "content-length" not in {k.lower() for k in large.request.headers}
    assert small.json() == {"size": 50}
    assert_error(large, 413, "PAYLOAD_TOO_LARGE")


# --- Rate limiting --------------------------------------------------------------------


def test_requests_over_rate_limit_get_429(make_client: MakeClient) -> None:
    client = make_client(rate_limit_per_minute=3, cors_origins=[ALLOWED_ORIGIN])
    headers = {"Origin": ALLOWED_ORIGIN}

    statuses = [client.get("/api/v1/specialties", headers=headers).status_code for _ in range(3)]
    limited = client.get("/api/v1/specialties", headers=headers)

    assert statuses == [200, 200, 200]
    assert_error(limited, 429, "RATE_LIMITED")
    assert 1 <= int(limited.headers["Retry-After"]) <= 60
    _assert_common_headers(limited)


def test_liveness_is_never_rate_limited(make_client: MakeClient) -> None:
    client = make_client(rate_limit_per_minute=3)

    statuses = [client.get("/api/v1/health/live").status_code for _ in range(10)]

    assert statuses == [200] * 10


def test_readiness_is_rate_limited(make_client: MakeClient) -> None:
    # Each readiness check runs a query, so it counts like any other request.
    client = make_client(rate_limit_per_minute=3)

    statuses = [client.get("/api/v1/health/ready").status_code for _ in range(4)]

    assert statuses == [200, 200, 200, 429]


# --- Errors keep their headers --------------------------------------------------------


def test_500_response_has_cors_and_request_id(make_client: MakeClient) -> None:
    client = make_client(cors_origins=[ALLOWED_ORIGIN])

    response = client.get(
        "/api/v1/_test/boom", headers={"Origin": ALLOWED_ORIGIN, "X-Request-ID": "trace-500"}
    )

    error = assert_error(response, 500, "INTERNAL_ERROR")
    assert error["request_id"] == "trace-500"
    _assert_common_headers(response)


# --- CORS -----------------------------------------------------------------------------


def test_cors_preflight_from_allowed_origin(make_client: MakeClient) -> None:
    client = make_client(cors_origins=[ALLOWED_ORIGIN])

    response = client.options(
        "/api/v1/providers",
        headers={
            "Origin": ALLOWED_ORIGIN,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "X-Request-ID",
        },
    )

    assert response.status_code == 200
    assert response.headers["Access-Control-Allow-Origin"] == ALLOWED_ORIGIN
    assert "Access-Control-Allow-Credentials" not in response.headers


def test_cors_preflight_from_other_origin_is_not_allowed(make_client: MakeClient) -> None:
    client = make_client(cors_origins=[ALLOWED_ORIGIN])

    response = client.options(
        "/api/v1/providers",
        headers={"Origin": OTHER_ORIGIN, "Access-Control-Request-Method": "GET"},
    )

    assert "Access-Control-Allow-Origin" not in response.headers


def test_cors_exposes_request_id_header(make_client: MakeClient) -> None:
    client = make_client(cors_origins=[ALLOWED_ORIGIN])

    response = client.get("/api/v1/health/live", headers={"Origin": ALLOWED_ORIGIN})

    _assert_common_headers(response)
    assert "x-request-id" in response.headers["Access-Control-Expose-Headers"].lower()
