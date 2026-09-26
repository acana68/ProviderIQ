"""Error types and handlers. Every error response has the same shape:

    {"error": {"code": "...", "message": "...", "request_id": "...", "details": [...]}}

`details` is only present for validation errors.
"""

import logging
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.request_context import get_request_id

logger = logging.getLogger(__name__)

# Codes for statuses that Starlette/FastAPI raise as HTTPException. Others fall back to
# the HTTPStatus name, e.g. 415 -> UNSUPPORTED_MEDIA_TYPE.
_HTTP_ERROR_CODES = {
    400: "BAD_REQUEST",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    413: "PAYLOAD_TOO_LARGE",
    429: "RATE_LIMITED",
}

# Where a parameter came from; dropped from the field path ("query.page_size" -> "page_size").
_LOCATION_PREFIXES = {"query", "path", "body", "header", "cookie"}


class AppError(Exception):
    """An error we raise on purpose; its message is safe to show to the client."""

    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found") -> None:
        super().__init__("NOT_FOUND", message, 404)


def error_response(
    status_code: int,
    code: str,
    message: str,
    details: list[dict[str, str]] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    error: dict[str, Any] = {"code": code, "message": message, "request_id": get_request_id()}
    if details is not None:
        error["details"] = details
    return JSONResponse({"error": error}, status_code=status_code, headers=headers)


def internal_error_response() -> JSONResponse:
    return error_response(500, "INTERNAL_ERROR", "An unexpected error occurred")


async def app_error_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)
    return error_response(exc.status_code, exc.code, exc.message)


async def validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    # Only the location and pydantic's message: never the submitted value ("input"),
    # which could be anything the client typed.
    details = []
    for error in exc.errors():
        location = list(error["loc"])
        if location and location[0] in _LOCATION_PREFIXES:
            location = location[1:]
        details.append({"field": ".".join(str(part) for part in location), "message": error["msg"]})
    return error_response(422, "VALIDATION_ERROR", "Request validation failed", details)


async def http_error_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    status = HTTPStatus(exc.status_code)
    code = _HTTP_ERROR_CODES.get(exc.status_code, status.name)
    message = exc.detail if isinstance(exc.detail, str) else status.phrase
    # Keep headers such as Allow on a 405.
    return error_response(exc.status_code, code, message, headers=exc.headers)


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Backstop for errors raised outside UnhandledErrorMiddleware (i.e. in other middleware).

    Normal route errors are turned into 500s by UnhandledErrorMiddleware instead, because
    Starlette runs this handler outside all user middleware, so its response gets no CORS
    or X-Request-ID headers.
    """
    logger.error("Unhandled error in middleware", exc_info=exc)
    return internal_error_response()


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)
