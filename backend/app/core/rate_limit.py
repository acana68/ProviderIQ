"""A small in-memory sliding-window rate limiter.

The counts live in this process's memory. With several app instances (or uvicorn workers)
each one counts separately, so a client effectively gets the limit once per process.
Running more than one instance means moving the counters to a shared store such as Redis.
"""

import math
import time
from collections import deque
from collections.abc import Callable, Collection

from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.errors import error_response


class SlidingWindowRateLimiter:
    """At most `limit` requests per key in any rolling window of `window_seconds`.

    Keeps one timestamp per allowed request (a sliding log), so it has no burst at window
    boundaries the way fixed per-minute buckets do. Rejected requests are not recorded.

    Not thread-safe; it's only called from the event loop, and hit() never awaits.
    """

    def __init__(
        self,
        limit: int,
        window_seconds: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._limit = limit
        self._window = window_seconds
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}
        self._next_sweep = clock() + window_seconds

    def hit(self, key: str) -> float | None:
        """Record a request for key. Returns None if allowed, else seconds until it would be."""
        now = self._clock()
        if now >= self._next_sweep:
            self._sweep(now)

        hits = self._hits.setdefault(key, deque())
        cutoff = now - self._window
        while hits and hits[0] <= cutoff:
            hits.popleft()
        if len(hits) >= self._limit:
            return hits[0] + self._window - now
        hits.append(now)
        return None

    def _sweep(self, now: float) -> None:
        """Forget clients with no requests in the last window, so memory stays bounded."""
        cutoff = now - self._window
        self._hits = {key: hits for key, hits in self._hits.items() if hits and hits[-1] > cutoff}
        self._next_sweep = now + self._window


def retry_after_header(seconds: float) -> str:
    """Retry-After takes whole seconds; round up so a client that waits isn't early."""
    return str(max(1, math.ceil(seconds)))


class RateLimitMiddleware:
    """Rejects requests over the limit with 429 RATE_LIMITED and a Retry-After header.

    Keyed by the socket peer address. X-Forwarded-For is deliberately ignored: any client
    can set it, so trusting it would let them pick their own rate-limit key. Behind a
    reverse proxy, run uvicorn with --forwarded-allow-ips so the peer address is correct.
    """

    def __init__(
        self,
        app: ASGIApp,
        limiter: SlidingWindowRateLimiter,
        exempt_paths: Collection[str] = (),
    ) -> None:
        self.app = app
        self.limiter = limiter
        self.exempt_paths = exempt_paths

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] in self.exempt_paths:
            await self.app(scope, receive, send)
            return

        client = scope.get("client")
        retry_after = self.limiter.hit(client[0] if client else "unknown")
        if retry_after is None:
            await self.app(scope, receive, send)
            return

        response = error_response(
            429,
            "RATE_LIMITED",
            "Too many requests; please retry later",
            headers={"Retry-After": retry_after_header(retry_after)},
        )
        await response(scope, receive, send)
