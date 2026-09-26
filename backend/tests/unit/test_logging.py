import json
import logging
import sys

from app.core.logging import JsonFormatter
from app.core.request_context import request_id_var


def _record(message: str = "hello", **extra: object) -> logging.LogRecord:
    record = logging.LogRecord("app.test", logging.INFO, __file__, 1, message, (), None)
    record.__dict__.update(extra)
    return record


def test_formats_one_json_object_with_extras() -> None:
    line = JsonFormatter().format(_record(method="GET", status=200))

    payload = json.loads(line)
    assert payload["level"] == "INFO"
    assert payload["logger"] == "app.test"
    assert payload["message"] == "hello"
    assert payload["method"] == "GET"
    assert payload["status"] == 200
    assert "request_id" not in payload
    assert "\n" not in line


def test_includes_request_id_when_set() -> None:
    token = request_id_var.set("req-42")
    try:
        payload = json.loads(JsonFormatter().format(_record()))
    finally:
        request_id_var.reset(token)

    assert payload["request_id"] == "req-42"


def test_includes_traceback_for_exceptions() -> None:
    try:
        raise ValueError("boom")
    except ValueError:
        record = logging.LogRecord(
            "app.test", logging.ERROR, __file__, 1, "failed", (), sys.exc_info()
        )

    payload = json.loads(JsonFormatter().format(record))

    assert "ValueError: boom" in payload["exc_info"]


def test_drops_uvicorn_color_message() -> None:
    payload = json.loads(
        JsonFormatter().format(_record(color_message="\x1b[32mhello\x1b[0m", status=200))
    )

    assert "color_message" not in payload
    assert payload["status"] == 200
