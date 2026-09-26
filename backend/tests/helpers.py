import csv
from collections.abc import Iterator
from contextlib import contextmanager
from functools import cache
from types import SimpleNamespace
from typing import Any

from httpx2 import Response
from sqlalchemy import Engine, event

from app.ai.vocabulary import Vocabulary, build_vocabulary
from scripts.generate_data import REFERENCE_DIR

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


def _reference_rows(name: str) -> list[dict[str, str]]:
    with (REFERENCE_DIR / name).open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


class CsvVocabularySource:
    """A VocabularySource over the reference CSVs, for tests without a database. Which
    specialties treat a condition comes from conditions.csv here, rather than from
    providers as in the app; the generated data links them the same way."""

    def list_specialties_with_provider_counts(self) -> list[SimpleNamespace]:
        rows = _reference_rows("specialties.csv")
        return [SimpleNamespace(slug=r["slug"], name=r["name"]) for r in rows]

    def list_conditions(self) -> list[SimpleNamespace]:
        rows = _reference_rows("conditions.csv")
        return [SimpleNamespace(slug=r["slug"], name=r["name"]) for r in rows]

    def list_condition_specialties(self) -> list[SimpleNamespace]:
        return [
            SimpleNamespace(condition_slug=r["slug"], specialty_slug=specialty)
            for r in _reference_rows("conditions.csv")
            for specialty in r["specialties"].split(";")
        ]

    def list_cities(self) -> list[SimpleNamespace]:
        rows = _reference_rows("cities.csv")
        return [SimpleNamespace(name=r["name"], state=r["state"]) for r in rows]


@cache
def reference_vocabulary() -> Vocabulary:
    return build_vocabulary(CsvVocabularySource())


class FakeLLMClient:
    """Stands in for the real LLM client: returns a canned response (or raises) and
    records every call."""

    def __init__(self, response: Any = None, error: BaseException | None = None) -> None:
        self.response = response
        self.error = error
        self.calls: list[dict[str, Any]] = []
        self.closed = False

    def complete_json(self, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        self.calls.append({"system": system, "user": user, "schema": schema})
        if self.error is not None:
            raise self.error
        return self.response

    def close(self) -> None:
        self.closed = True
