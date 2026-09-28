"""Pure ASGI middleware (not BaseHTTPMiddleware), so request bodies stream through
untouched and contextvars set here are visible in the route and its log lines."""

import logging
import re
import time
import uuid

from fastapi import FastAPI
from starlette.datastructures import Headers, MutableHeaders
from starlette.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import Settings
from app.core.errors import error_response, internal_error_response
from app.core.rate_limit import RateLimitMiddleware, SlidingWindowRateLimiter
from app.core.request_context import request_id_var

logger = logging.getLogger(__name__)
access_logger = logging.getLogger("app.access")

REQUEST_ID_HEADER = "X-Request-ID"
_VALID_REQUEST_ID = re.compile(r"[A-Za-z0-9_-]{1,64}")


def install_middleware(app: FastAPI, settings: Settings) -> None:
    """Add middleware, listed outermost first.

    The order matters: responses produced by an inner layer (413, 429, 500) pass back out
    through CORS and RequestContext, so they still get CORS and X-Request-ID headers.
    """
    limiter = SlidingWindowRateLimiter(settings.rate_limit_per_minute)
    layers = [
        (RequestContextMiddleware, {}),
        (
            CORSMiddleware,
            {
                "allow_origins": settings.cors_origins,
                "allow_methods": ["GET", "POST"],
                "allow_headers": ["Content-Type", REQUEST_ID_HEADER],
                "expose_headers": [REQUEST_ID_HEADER],
                "allow_credentials": False,
            },
        ),
        (
            RateLimitMiddleware,
            {"limiter": limiter, "exempt_paths": {f"{settings.api_prefix}/health/live"}},
        ),
        (BodySizeLimitMiddleware, {"max_bytes": settings.max_request_body_bytes}),
        (UnhandledErrorMiddleware, {}),
    ]
    # add_middleware() inserts at the front, so add innermost first.
    for middleware_class, options in reversed(layers):
        app.add_middleware(middleware_class, **options)


class RequestContextMiddleware:
    """Request ID, access log, and security headers.

    Accepts the caller's X-Request-ID if it looks safe (it ends up in logs), otherwise
    generates one. Writes one access-log line per request, without the query string.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = Headers(scope=scope).get(REQUEST_ID_HEADER)
        valid = incoming is not None and _VALID_REQUEST_ID.fullmatch(incoming)
        request_id = incoming if valid else str(uuid.uuid4())
        token = request_id_var.set(request_id)
        start = time.perf_counter()
        # Stays 500 if the app raises before starting a response.
        status_code = 500

        async def send_with_headers(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = MutableHeaders(scope=message)
                headers[REQUEST_ID_HEADER] = request_id
                headers["X-Content-Type-Options"] = "nosniff"
            await send(message)

        try:
            await self.app(scope, receive, send_with_headers)
        finally:
            access_logger.info(
                "request",
                extra={
                    "method": scope["method"],
                    "path": scope["path"],
                    "status": status_code,
                    "duration_ms": round((time.perf_counter() - start) * 1000, 2),
                },
            )
            request_id_var.reset(token)


class BodySizeLimitMiddleware:
    """Rejects request bodies larger than max_bytes with 413 PAYLOAD_TOO_LARGE.

    With a Content-Length header the check happens before reading anything; the server
    (h11/httptools) guarantees the body matches that length. Without one (chunked
    uploads), the body is buffered up to the limit and replayed to the app. That costs at
    most max_bytes of memory per request, which is small at our limit.
    """

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        content_length = Headers(scope=scope).get("content-length")
        if content_length is not None:
            if not content_length.isdigit():
                response = error_response(400, "BAD_REQUEST", "Invalid Content-Length header")
                await response(scope, receive, send)
            elif int(content_length) > self.max_bytes:
                await self._reject(scope, receive, send)
            else:
                await self.app(scope, receive, send)
            return

        chunks: list[bytes] = []
        size = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > self.max_bytes:
                await self._reject(scope, receive, send)
                return
            chunks.append(chunk)
            if not message.get("more_body", False):
                break

        body = b"".join(chunks)
        replayed = False

        async def replay_receive() -> Message:
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": body, "more_body": False}
            # After the body, pass through so the app still sees http.disconnect.
            return await receive()

        await self.app(scope, replay_receive, send)

    async def _reject(self, scope: Scope, receive: Receive, send: Send) -> None:
        response = error_response(
            413,
            "PAYLOAD_TOO_LARGE",
            f"Request body exceeds the {self.max_bytes}-byte limit",
        )
        await response(scope, receive, send)


class UnhandledErrorMiddleware:
    """Turns any exception from a route into a generic 500 INTERNAL_ERROR.

    The traceback is logged server-side only. This sits inside CORS and RequestContext
    (unlike Starlette's own Exception handler, which runs outside all user middleware),
    so 500 responses carry the same headers as every other response.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        response_started = False

        async def tracking_send(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, receive, tracking_send)
        except Exception:
            logger.exception(
                "Unhandled error", extra={"method": scope["method"], "path": scope["path"]}
            )
            if response_started:
                # Too late to send a different response; let the server close the connection.
                raise
            await internal_error_response()(scope, receive, send)
