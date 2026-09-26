from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from httpx2 import Response
from sqlalchemy import Engine, event

# Raised by the test-only /_test/boom route (see conftest); must never reach a response body.
SECRET_ERROR_DETAIL = "db password is hunter2"


def assert_error(response: Response, status_code: int, code: str) -> dict[str, Any]:
    """Assert the standard error shape and return the inner "error" object."""
    assert response.status_code == status_code, response.text
    body = response.json()
    assert set(body) == {"error"}
    error = body["error"]
    assert error["code"] == code
    assert isinstance(error["message"], str) and error["message"]
    assert error["request_id"] == response.headers["X-Request-ID"]
    return error


@contextmanager
def count_selects(engine: Engine) -> Iterator[list[str]]:
    """Collects the SELECT statements the engine runs inside the block."""
    statements: list[str] = []

    def record(conn: object, cursor: object, statement: str, *args: object) -> None:
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    event.listen(engine, "before_cursor_execute", record)
    try:
        yield statements
    finally:
        event.remove(engine, "before_cursor_execute", record)
