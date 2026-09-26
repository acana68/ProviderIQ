import math
from http import HTTPStatus
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

# Two letters in any case, normalized to uppercase ("ny" -> "NY").
StateCode = Annotated[str, StringConstraints(pattern=r"^[A-Za-z]{2}$", to_upper=True)]

# Shared by search requests and AI-parsed criteria, so the two always have the same shape.
MAX_RADIUS_MILES = 100.0
Slug = Annotated[str, StringConstraints(min_length=1, max_length=100)]
CityName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
RadiusMiles = Annotated[float, Field(ge=1, le=MAX_RADIUS_MILES)]
# Which parser turned natural language into criteria.
ParserUsed = Literal["llm", "rule_based"]


class Location(BaseModel):
    model_config = ConfigDict(extra="forbid")

    city: CityName
    state: StateCode


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
