"""AnthropicClient against a stub SDK client: checks the exact request it sends and how it
reads the reply, without any network access."""

from types import SimpleNamespace
from typing import Any

import pytest

from app.ai.llm_client import MAX_TOKENS, TOOL_NAME, AnthropicClient, LLMResponseError

SCHEMA = {"type": "object", "properties": {"specialty": {"type": "string"}}}


class StubMessages:
    def __init__(self, response: Any) -> None:
        self.response = response
        self.kwargs: dict[str, Any] = {}

    def create(self, **kwargs: Any) -> Any:
        self.kwargs = kwargs
        return self.response


def _client(response: Any) -> tuple[AnthropicClient, StubMessages]:
    messages = StubMessages(response)
    sdk = SimpleNamespace(messages=messages, close=lambda: None)
    client = AnthropicClient(
        api_key="unused", model="test-model", timeout_seconds=3, sdk_client=sdk
    )
    return client, messages


def _response(*content: Any, stop_reason: str = "tool_use") -> SimpleNamespace:
    return SimpleNamespace(content=list(content), stop_reason=stop_reason)


def _tool_use(input_: Any, name: str = TOOL_NAME) -> SimpleNamespace:
    return SimpleNamespace(type="tool_use", name=name, input=input_)


def test_forces_the_criteria_tool_and_returns_its_input() -> None:
    client, messages = _client(_response(_tool_use({"specialty": "cardiology"})))

    result = client.complete_json("system text", "<query>q</query>", SCHEMA)

    assert result == {"specialty": "cardiology"}
    sent = messages.kwargs
    assert sent["model"] == "test-model"
    assert sent["system"] == "system text"
    assert sent["messages"] == [{"role": "user", "content": "<query>q</query>"}]
    assert sent["tools"] == [
        {"name": TOOL_NAME, "description": sent["tools"][0]["description"], "input_schema": SCHEMA}
    ]
    assert sent["tool_choice"] == {"type": "tool", "name": TOOL_NAME}
    assert sent["max_tokens"] == MAX_TOKENS <= 1024
    assert sent["extra_body"] == {"temperature": 0}


@pytest.mark.parametrize(
    "response",
    [
        pytest.param(_response(_tool_use({}), stop_reason="max_tokens"), id="truncated"),
        pytest.param(_response(stop_reason="refusal"), id="refusal"),
        pytest.param(
            _response(SimpleNamespace(type="text", text="Sure!"), stop_reason="tool_use"),
            id="no tool call",
        ),
        pytest.param(_response(_tool_use({}, name="other_tool")), id="wrong tool"),
        pytest.param(_response(_tool_use(["not", "an", "object"])), id="non-object input"),
    ],
)
def test_anything_but_a_complete_tool_call_raises(response: Any) -> None:
    client, _ = _client(response)

    with pytest.raises(LLMResponseError):
        client.complete_json("s", "u", SCHEMA)


def test_real_sdk_client_is_configured_without_retries() -> None:
    # Constructing the SDK client makes no network call.
    client = AnthropicClient(api_key="sk-test-not-real", model="m", timeout_seconds=4)

    assert client._client.max_retries == 0
    assert client._client.timeout == 4
    client.close()
