"""Smoke test for a running ProviderIQ: API, database, seed data, and the frontend shell.

Standard library only, so it runs anywhere Python does (CI, a fresh machine, a server),
without the backend's virtualenv.

    python backend/scripts/smoke_test.py                        # http://localhost:8080
    python backend/scripts/smoke_test.py https://example.com

Exits 0 when every check passes; otherwise prints what failed and exits 1.
"""

import argparse
import json
import sys
import urllib.error
import urllib.request
from typing import Any

DEFAULT_BASE_URL = "http://localhost:8080"
EXPECTED_SPECIALTIES = 10


class SmokeTestFailure(Exception):
    pass


def request(
    base_url: str, path: str, *, body: Any = None, timeout: float = 10
) -> tuple[int, dict[str, str], bytes]:
    """(status, headers, body). HTTP errors are returned, not raised; network errors raise."""
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}",
        data=data,
        method="GET" if body is None else "POST",
        headers={"Accept": "*/*", **({"Content-Type": "application/json"} if data else {})},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status, dict(response.headers), response.read()
    except urllib.error.HTTPError as error:
        return error.code, dict(error.headers), error.read()
    except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
        reason = getattr(error, "reason", error)
        raise SmokeTestFailure(f"{path}: could not connect to {base_url} ({reason})") from None


def get_json(base_url: str, path: str, *, body: Any = None) -> Any:
    status, _headers, raw = request(base_url, path, body=body)
    if status != 200:
        raise SmokeTestFailure(f"{path}: expected HTTP 200, got {status}: {raw[:200]!r}")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        raise SmokeTestFailure(f"{path}: response is not JSON: {raw[:200]!r}") from None


def check_health(base_url: str) -> str:
    live = get_json(base_url, "/api/v1/health/live")
    if live.get("status") != "ok":
        raise SmokeTestFailure(f"/api/v1/health/live: not live: {live}")
    ready = get_json(base_url, "/api/v1/health/ready")
    if ready.get("status") != "ok" or ready.get("database") != "ok":
        raise SmokeTestFailure(f"/api/v1/health/ready: not ready: {ready}")
    return "live, ready, database ok"


def check_specialties(base_url: str) -> str:
    specialties = get_json(base_url, "/api/v1/specialties")
    if not isinstance(specialties, list) or len(specialties) != EXPECTED_SPECIALTIES:
        count = len(specialties) if isinstance(specialties, list) else "not a list"
        raise SmokeTestFailure(
            f"/api/v1/specialties: expected {EXPECTED_SPECIALTIES}, got {count}"
            " (has the database been seeded?)"
        )
    return f"{len(specialties)} specialties"


def check_search(base_url: str) -> str:
    results = get_json(
        base_url,
        "/api/v1/search",
        body={"specialty": "cardiology", "location": {"city": "New York", "state": "NY"}},
    )
    items = results.get("items") or []
    if not items:
        raise SmokeTestFailure("/api/v1/search: no cardiologists near New York")
    for item in items:
        overall = item.get("score", {}).get("overall")
        if not isinstance(overall, (int, float)) or not 0 <= overall <= 100:
            raise SmokeTestFailure(f"/api/v1/search: result without a valid score: {item}")
    top = items[0]
    return (
        f"{results.get('total')} cardiologists near New York; top: "
        f"{top['provider']['display_name']} ({top['score']['overall']})"
    )


def check_app_shell(base_url: str) -> str:
    # "/" and a client-side route must both get the SPA's index.html.
    for path in ("/", "/results?specialty=cardiology"):
        status, headers, raw = request(base_url, path)
        content_type = {k.lower(): v for k, v in headers.items()}.get("content-type", "")
        if status != 200 or "text/html" not in content_type:
            raise SmokeTestFailure(f"{path}: expected HTML with 200, got {status} {content_type}")
        if b'<div id="root">' not in raw:
            raise SmokeTestFailure(f"{path}: HTML is not the app shell (no #root element)")
    return "app shell served at / and for client-side routes"


CHECKS = [check_health, check_specialties, check_search, check_app_shell]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("base_url", nargs="?", default=DEFAULT_BASE_URL)
    args = parser.parse_args()

    print(f"Smoke testing {args.base_url}")
    for check in CHECKS:
        try:
            print(f"  ok    {check(args.base_url)}")
        except SmokeTestFailure as failure:
            print(f"  FAIL  {failure}", file=sys.stderr)
            return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
