"""BodySizeLimitMiddleware driven directly over ASGI, to control exactly how the body is
chunked (the HTTP test client always delivers it in a single message)."""

import asyncio
import json

from starlette.types import Message, Receive, Scope, Send

from app.core.middleware import BodySizeLimitMiddleware


async def _echo_body_size(scope: Scope, receive: Receive, send: Send) -> None:
    body = b""
    while True:
        message = await receive()
        body += message.get("body", b"")
        if not message.get("more_body", False):
            break
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": str(len(body)).encode()})


def _run(chunks: list[bytes], headers: list[tuple[bytes, bytes]]) -> tuple[int, bytes]:
    messages: list[Message] = [
        {"type": "http.request", "body": chunk, "more_body": i < len(chunks) - 1}
        for i, chunk in enumerate(chunks)
    ]
    sent: list[Message] = []

    async def receive() -> Message:
        return messages.pop(0) if messages else {"type": "http.disconnect"}

    async def send(message: Message) -> None:
        sent.append(message)

    scope = {"type": "http", "method": "POST", "path": "/", "headers": headers}
    asyncio.run(BodySizeLimitMiddleware(_echo_body_size, max_bytes=100)(scope, receive, send))
    body = b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")
    return sent[0]["status"], body


def test_chunked_body_under_limit_is_replayed_whole() -> None:
    status, body = _run([b"x" * 40, b"x" * 40, b"x" * 20], headers=[])

    assert status == 200
    assert body == b"100"


def test_chunked_body_over_limit_is_rejected_mid_stream() -> None:
    status, body = _run([b"x" * 60, b"x" * 60, b"x" * 60], headers=[])

    assert status == 413
    assert json.loads(body)["error"]["code"] == "PAYLOAD_TOO_LARGE"


def test_invalid_content_length_is_rejected() -> None:
    status, body = _run([b"x"], headers=[(b"content-length", b"abc")])

    assert status == 400
    assert json.loads(body)["error"]["code"] == "BAD_REQUEST"
