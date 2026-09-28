"""Which client address the rate limiters see behind the bundled nginx.

The Docker entrypoint runs uvicorn with --proxy-headers and --forwarded-allow-ips set to
nginx's fixed address (docker-compose.yml), and nginx appends its peer to
X-Forwarded-For. These tests put uvicorn's own ProxyHeadersMiddleware, configured the
same way, in front of the app.
"""

import asyncio
import ipaddress
import re
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.core.config import REPO_ROOT, Settings
from app.main import create_app

COMPOSE_FILE = REPO_ROOT / "docker-compose.yml"
CLIENT_A = "203.0.113.7"
CLIENT_B = "203.0.113.8"
SPOOFED = "198.51.100.1"


def _compose_value(pattern: str) -> str:
    match = re.search(pattern, COMPOSE_FILE.read_text(encoding="utf-8"), re.MULTILINE)
    assert match, f"{pattern!r} not found in docker-compose.yml"
    return match.group(1)


NGINX_IP = _compose_value(r"^x-nginx-ip: &nginx-ip (\S+)$")


def _through_nginx(client_ip: str, sent: str | None = None) -> str:
    """X-Forwarded-For as nginx forwards it: $proxy_add_x_forwarded_for appends the
    client's address to whatever the client sent."""
    return client_ip if sent is None else f"{sent}, {client_ip}"


def test_nginx_address_is_inside_the_compose_subnet() -> None:
    subnet = _compose_value(r"^\s+- subnet: (\S+)$")

    assert ipaddress.ip_address(NGINX_IP) in ipaddress.ip_network(subnet)


def test_compose_trusts_only_nginx() -> None:
    assert _compose_value(r"^\s+FORWARDED_ALLOW_IPS: (\S+)$") == "*nginx-ip"


@pytest.fixture
def client_seen() -> Callable[..., str]:
    """The client host the app sees for a request from peer with these XFF values."""

    def seen(peer: str, *forwarded_for: str) -> str:
        captured: dict[str, Any] = {}

        async def app(scope: Any, receive: Any, send: Any) -> None:
            captured["client"] = scope["client"][0]

        middleware = ProxyHeadersMiddleware(app, trusted_hosts=NGINX_IP)
        scope = {
            "type": "http",
            "scheme": "http",
            "client": (peer, 40000),
            "headers": [(b"x-forwarded-for", value.encode()) for value in forwarded_for],
        }
        asyncio.run(middleware(scope, None, None))
        return captured["client"]

    return seen


def test_client_address_comes_from_nginx(client_seen: Callable[..., str]) -> None:
    assert client_seen(NGINX_IP, _through_nginx(CLIENT_A)) == CLIENT_A


@pytest.mark.parametrize("sent", [SPOOFED, f"{SPOOFED}, {CLIENT_B}", NGINX_IP, "garbage"])
def test_addresses_the_client_writes_into_the_header_are_ignored(
    client_seen: Callable[..., str], sent: str
) -> None:
    # nginx appends the real peer last; uvicorn takes the rightmost untrusted entry.
    assert client_seen(NGINX_IP, _through_nginx(CLIENT_A, sent)) == CLIENT_A


def test_header_from_anyone_but_nginx_is_ignored(client_seen: Callable[..., str]) -> None:
    assert client_seen(CLIENT_A, SPOOFED) == CLIENT_A


@pytest.fixture
def via_nginx() -> Callable[[], TestClient]:
    """Clients for one app (limit: 3 a minute) behind uvicorn's proxy handling, all
    connecting from nginx's address. The requests 404 without touching the database."""
    settings = Settings(
        _env_file=None,
        environment="test",
        database_url="postgresql+psycopg://unused@localhost/unused",
        rate_limit_per_minute=3,
        # Never a real LLM client, whatever the environment says.
        ai_provider="none",
        anthropic_api_key=None,
    )
    app = create_app(settings)
    proxied = ProxyHeadersMiddleware(app, trusted_hosts=NGINX_IP)
    return lambda: TestClient(proxied, client=(NGINX_IP, 40000))


def _statuses(client: TestClient, forwarded_for: str, n: int) -> list[int]:
    return [
        client.get("/api/v1/_missing", headers={"X-Forwarded-For": forwarded_for}).status_code
        for _ in range(n)
    ]


def test_two_clients_through_nginx_get_separate_buckets(
    via_nginx: Callable[[], TestClient],
) -> None:
    client = via_nginx()

    assert _statuses(client, _through_nginx(CLIENT_A), 4) == [404, 404, 404, 429]
    # Client A is limited; client B, through the same nginx, still has its whole budget.
    assert _statuses(client, _through_nginx(CLIENT_B), 3) == [404, 404, 404]


def test_a_limited_client_cannot_escape_by_forging_the_header(
    via_nginx: Callable[[], TestClient],
) -> None:
    client = via_nginx()
    _statuses(client, _through_nginx(CLIENT_A), 3)

    forged = [_through_nginx(CLIENT_A, f"198.51.100.{i}") for i in range(5)]

    assert [_statuses(client, header, 1)[0] for header in forged] == [429] * 5
