"""Thin wrapper around the Anthropic SDK with a structured-output helper.

Instead of asking Claude for free-text JSON and hoping it parses, every agent
in this project forces a tool call whose input schema *is* the desired shape.
That input is already valid JSON matching the schema, so there's no brittle
parsing/repair step.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import anthropic
from tenacity import retry, retry_if_not_exception_type, stop_after_attempt, wait_random_exponential

from src.config import load_settings

# Config errors (e.g. a missing API key) can't be fixed by retrying - retry
# only transient failures (rate limits, network blips) so the real message
# reaches the caller instead of a RetryError wrapping it.
_retry = retry(
    wait=wait_random_exponential(min=1, max=20),
    stop=stop_after_attempt(4),
    retry=retry_if_not_exception_type(RuntimeError),
)


@lru_cache(maxsize=1)
def _client() -> anthropic.Anthropic:
    settings = load_settings()
    if not settings.anthropic_api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add your key."
        )
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


@_retry
def call_structured(
    *,
    system: str,
    user: str,
    tool_name: str,
    tool_description: str,
    input_schema: dict[str, Any],
    max_tokens: int = 1024,
) -> dict[str, Any]:
    """Call Claude and force it to respond via a single tool call, returning that tool's input."""
    settings = load_settings()
    response = _client().messages.create(
        model=settings.anthropic_model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
        tools=[
            {
                "name": tool_name,
                "description": tool_description,
                "input_schema": input_schema,
            }
        ],
        tool_choice={"type": "tool", "name": tool_name},
    )
    for block in response.content:
        if block.type == "tool_use" and block.name == tool_name:
            return block.input
    raise RuntimeError(f"Claude did not return the expected tool call '{tool_name}'")


@_retry
def call_text(*, system: str, user: str, max_tokens: int = 2048) -> str:
    """Plain-text completion, used for the final free-form synthesis writeup."""
    settings = load_settings()
    response = _client().messages.create(
        model=settings.anthropic_model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(block.text for block in response.content if block.type == "text")
