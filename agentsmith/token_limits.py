"""agentsmith/token_limits.py — tokens bounded per role and per run
(.agent-rfc/designs/run-token-limits.md).

Counting tokens is not the same as using fewer. These limits are off until a tenant
declares them, and each refuses before anything is sent:

    models.yaml  max_output_tokens   the answer, capped per role
                 max_input_tokens    a prompt estimated larger is refused
    tenant.yaml  limits.run_tokens       one workflow run's token budget
                 limits.run_tool_calls   one workflow run's tool calls

Run counters go through the gateway's budget backend, whose `try_reserve` is atomic,
so concurrent calls in one run cannot overshoot. A size known only after the call is
estimated before it at four characters a token.
"""

from __future__ import annotations

from typing import Any, Optional

RUN_TOKENS_ENV = "AGENTSMITH_RUN_TOKEN_LIMIT"
RUN_TOOL_CALLS_ENV = "AGENTSMITH_RUN_TOOL_CALL_LIMIT"


class ContextTooLargeError(ValueError):
    """A prompt larger than its role's declared `max_input_tokens`."""


class RunLimitExceededError(RuntimeError):
    """A workflow run would pass its declared token budget."""


class ToolCallLimitExceededError(RuntimeError):
    """A workflow run would pass its declared tool-call limit."""


def estimate_tokens(messages: Any) -> int:
    from agentsmith.prompt_identity import content_text

    if isinstance(messages, str):
        return len(messages) // 4
    total = 0
    for message in messages or []:
        content = message.get("content") if isinstance(message, dict) else message
        total += len(content_text(content))
    return total // 4


def _positive(value: Any) -> Optional[int]:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def output_cap(cfg: dict, requested: int) -> int:
    cap = _positive(cfg.get("max_output_tokens"))
    return min(requested, cap) if cap else requested


def check_input(cfg: dict, messages: Any, role: str) -> None:
    cap = _positive(cfg.get("max_input_tokens"))
    if cap is None:
        return
    size = estimate_tokens(messages)
    if size > cap:
        raise ContextTooLargeError(
            f"role {role!r} accepts at most {cap} input tokens (max_input_tokens in models.yaml); this prompt is "
            f"about {size}. Send less: summarise the history, or retrieve fewer passages.")


def _limit(dotted: str, env_var: str) -> Optional[int]:
    from agentsmith.config import resolve

    return _positive(resolve(dotted, env_var=env_var, default=None))


def run_token_limit() -> Optional[int]:
    return _limit("limits.run_tokens", RUN_TOKENS_ENV)


def run_tool_call_limit() -> Optional[int]:
    return _limit("limits.run_tool_calls", RUN_TOOL_CALLS_ENV)


def _run_key(kind: str, tenant_id: str, run_id: str) -> str:
    return f"run-{kind}:{tenant_id}:{run_id}"


def reserve_run(backend: Any, tenant_id: str, run_id: Optional[str], messages: Any, max_tokens: int) -> int:
    """Reserve this call's estimate against the run's budget; the amount reserved, or 0
    when the run has no budget. Raises when the call would pass it."""
    limit = run_token_limit()
    if limit is None or not run_id:
        return 0
    estimate = estimate_tokens(messages) + max_tokens
    if not backend.try_reserve(_run_key("tokens", tenant_id, run_id), estimate, limit):
        spent = backend.get_spend(_run_key("tokens", tenant_id, run_id))
        raise RunLimitExceededError(
            f"run {run_id!r} has spent about {int(spent)} of its {limit} tokens (limits.run_tokens); this call "
            f"would need about {estimate} more. Stopped before it was sent.")
    return estimate


def settle_run(backend: Any, tenant_id: str, run_id: Optional[str], reserved: int,
               input_tokens: Optional[int], output_tokens: Optional[int]) -> None:
    """Replace the estimate with the real count. With no usage reported the estimate stands."""
    if not reserved or not run_id or input_tokens is None or output_tokens is None:
        return
    delta = int(input_tokens) + int(output_tokens) - reserved
    if delta:
        backend.add_spend(_run_key("tokens", tenant_id, run_id), delta)


def release_run(backend: Any, tenant_id: str, run_id: Optional[str], reserved: int) -> None:
    """A call that failed spent nothing against the run."""
    if reserved and run_id:
        backend.add_spend(_run_key("tokens", tenant_id, run_id), -reserved)


def reserve_tool_call(backend: Any, tenant_id: str, run_id: Optional[str]) -> None:
    limit = run_tool_call_limit()
    if limit is None or not run_id:
        return
    if not backend.try_reserve(_run_key("tools", tenant_id, run_id), 1, limit):
        raise ToolCallLimitExceededError(
            f"run {run_id!r} has made its {limit} tool calls (limits.run_tool_calls). Stopped before the next.")
