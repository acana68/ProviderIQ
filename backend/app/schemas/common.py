import math
from http import HTTPStatus
from typing import Any, Literal, Self

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    app: str
    version: str
    environment: str
    database: Literal["ok", "unavailable"]


class Page[T](BaseModel):
    items: list[T]
    page: int
    page_size: int
    total: int
    total_pages: int

    @classmethod
    def build(cls, items: list[T], *, page: int, page_size: int, total: int) -> Self:
        return cls(
            items=items,
            page=page,
            page_size=page_size,
            total=total,
            total_pages=math.ceil(total / page_size),
        )


class ErrorDetail(BaseModel):
    field: str
    message: str


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: str | None
    details: list[ErrorDetail] | None = None


class ErrorResponse(BaseModel):
    """The shape of every error response (see core/errors.py). Used for OpenAPI docs."""

    error: ErrorBody


def error_responses(*status_codes: int) -> dict[int | str, dict[str, Any]]:
    """OpenAPI `responses=` entries that document our error shape for these statuses.

    Declaring 422 here also stops FastAPI from documenting its default validation shape,
    which the handlers in core/errors.py replace.
    """
    return {
        code: {"model": ErrorResponse, "description": HTTPStatus(code).phrase}
        for code in status_codes
    }
