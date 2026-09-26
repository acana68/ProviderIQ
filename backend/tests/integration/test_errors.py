import logging
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from tests.helpers import SECRET_ERROR_DETAIL, assert_error


def test_wrong_method_returns_405(client: TestClient) -> None:
    response = client.delete("/api/v1/specialties")

    assert_error(response, 405, "METHOD_NOT_ALLOWED")
    assert response.headers["Allow"] == "GET"


def test_validation_error_lists_fields_without_echoing_input(client: TestClient) -> None:
    submitted = "sneaky-value-1234"

    response = client.get("/api/v1/providers", params={"page_size": submitted, "state": submitted})

    error = assert_error(response, 422, "VALIDATION_ERROR")
    assert {detail["field"] for detail in error["details"]} == {"page_size", "state"}
    assert all(set(detail) == {"field", "message"} for detail in error["details"])
    assert submitted not in response.text


def test_unhandled_error_returns_generic_500(
    make_client: Callable[..., TestClient], caplog: pytest.LogCaptureFixture
) -> None:
    client = make_client()

    response = client.get("/api/v1/_test/boom")

    error = assert_error(response, 500, "INTERNAL_ERROR")
    assert error["message"] == "An unexpected error occurred"
    assert SECRET_ERROR_DETAIL not in response.text
    assert "Traceback" not in response.text
    # The details go to the server log instead.
    [record] = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert record.exc_info is not None
    assert SECRET_ERROR_DETAIL in str(record.exc_info[1])
