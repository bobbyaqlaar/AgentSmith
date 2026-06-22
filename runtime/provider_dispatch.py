"""
runtime/provider_dispatch.py — shared Anthropic-vs-OpenAI-compatible request
building and response parsing.

Before this module existed, runtime/llm_gateway.py and scripts/cost_router.py
each independently built provider request bodies/headers and parsed
responses, with no shared code — a fix to one (e.g. handling a new response
shape, a new provider quirk) would not propagate to the other
(FIXES_AND_CLEANUP.md 4.3). Only the provider-dispatch shape is shared here;
each caller's own routing/budget/degrade-ladder logic (which legitimately
differs between the dev-mode cost_router.py and the production
llm_gateway.py) stays in its own file.
"""

from __future__ import annotations

from typing import Any


def infer_provider(base_url: str) -> str:
    """cost_router.py only has a base_url (no separate provider field) — this
    mirrors its existing "anthropic" in base_url check."""
    return "anthropic" if "anthropic" in base_url else "openai_compatible"


def build_request(
    provider: str,
    model_id: str,
    messages: list[dict],
    api_key: str,
    max_tokens: int,
    temperature: float = 0.2,
) -> tuple[str, dict, dict]:
    """Returns (url_path, headers, body) for the given provider.

    provider="anthropic" uses the Messages API shape (system pulled out of
    the messages list into its own top-level field); anything else is
    treated as OpenAI-compatible (openai, groq, ollama, ...).
    """
    if provider == "anthropic":
        system = "\n".join(m["content"] for m in messages if m["role"] == "system") or None
        user_messages = [m for m in messages if m["role"] != "system"]
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        body: dict[str, Any] = {"model": model_id, "max_tokens": max_tokens, "messages": user_messages}
        if system:
            body["system"] = system
        return "/v1/messages", headers, body

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    body = {"model": model_id, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
    return "/chat/completions", headers, body


def parse_response(provider: str, data: dict) -> tuple[str, int, int]:
    """Returns (text, input_tokens, output_tokens)."""
    if provider == "anthropic":
        text = data["content"][0]["text"]
        usage = data.get("usage", {})
        return text, usage.get("input_tokens", 0), usage.get("output_tokens", 0)

    text = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {})
    return text, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)
