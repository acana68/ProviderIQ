"""LLM access behind a one-method interface, so the parser doesn't depend on a provider."""

from typing import Any, Protocol

import anthropic

# The one tool the model is forced to call; its input is the parsed criteria.
TOOL_NAME = "record_search_criteria"
TOOL_DESCRIPTION = "Record the provider-search filters described in the user's query."
# The criteria object is small; this leaves plenty of room without inviting rambling.
MAX_TOKENS = 512


class LLMClient(Protocol):
    def complete_json(self, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        """Ask the model for one JSON object matching `schema`. Raises on any failure."""
        ...


class LLMResponseError(Exception):
    """The model replied, but not with the expected structured output."""


class AnthropicClient:
    """Claude via the official SDK, using forced tool use for structured output.

    A single tool whose input_schema is the criteria schema, with tool_choice forcing that
    tool, so the reply is always a tool call whose input is the JSON object. (Nothing is
    executed: the "tool" is only a typed container for the answer.)

    Forced tool_choice and temperature both work on Claude Haiku 4.5, the default model.
    Some newer models reject one or the other with a 400; if AI_MODEL changes, check
    that parsing still reports parser_used="llm".
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_seconds: float,
        sdk_client: anthropic.Anthropic | None = None,
    ) -> None:
        self._model = model
        # max_retries=0: a retry would double the wait, and the fallback parser is instant.
        self._client = sdk_client or anthropic.Anthropic(
            api_key=api_key, timeout=timeout_seconds, max_retries=0
        )

    def complete_json(self, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": user}],
            tools=[{"name": TOOL_NAME, "description": TOOL_DESCRIPTION, "input_schema": schema}],
            tool_choice={"type": "tool", "name": TOOL_NAME},
            # Deterministic parsing. SDK 1.x dropped `temperature` from create()'s
            # signature, but the API still honours it for this model, so it goes in the body.
            extra_body={"temperature": 0},
        )
        # Anything else (max_tokens, refusal, ...) means no complete tool call.
        if response.stop_reason != "tool_use":
            raise LLMResponseError(f"unexpected stop_reason: {response.stop_reason}")
        for block in response.content:
            if block.type == "tool_use" and block.name == TOOL_NAME:
                if not isinstance(block.input, dict):
                    raise LLMResponseError("tool input is not a JSON object")
                return block.input
        raise LLMResponseError("response has no call to the criteria tool")

    def close(self) -> None:
        self._client.close()
